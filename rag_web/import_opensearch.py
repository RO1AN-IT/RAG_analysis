#!/usr/bin/env python3
"""
Скрипт для импорта индексов в новый OpenSearch сервер.
Используйте этот скрипт после экспорта данных через export_opensearch.py.

Использование:
    python import_opensearch.py
"""

import json
import sys
import os
from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
from typing import List, Dict, Any, Iterator, Tuple

# Попытка импорта ijson для потокового парсинга больших JSON
try:
    import ijson
    HAS_IJSON = True
except ImportError:
    HAS_IJSON = False

# Конфигурация нового OpenSearch
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', 'localhost')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
# По умолчанию False, потому что docker-compose.opensearch.yml запускает OpenSearch БЕЗ SSL (plugins.security.disabled=true)
# Для работы через HTTP используйте OPENSEARCH_USE_SSL=False
# Если включите SSL в OpenSearch, установите OPENSEARCH_USE_SSL=True
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
# Настройка аутентификации (поддержка обоих вариантов имен переменных)
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME') or os.environ.get('OPENSEARCH_AUTH_USERNAME')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD') or os.environ.get('OPENSEARCH_AUTH_PASSWORD')

# Директория с экспортированными данными
EXPORT_DIR = 'opensearch_export'

# Размер батча для bulk insert (уменьшен для экономии памяти)
BATCH_SIZE = 100

# Порог размера файла для использования потокового парсинга (MB)
STREAMING_THRESHOLD_MB = 500


def stream_documents_from_json(filename: str) -> Iterator[Dict[str, Any]]:
    """
    Потоковое чтение документов из JSON файла экспорта.
    Использует ijson для парсинга без загрузки всего файла в память.
    
    Args:
        filename: Путь к JSON файлу
        
    Yields:
        Словари документов по одному
    """
    if not HAS_IJSON:
        raise ImportError("ijson не установлен. Установите: pip install ijson")
    
    with open(filename, 'rb') as f:
        # Парсим массив documents потоково
        parser = ijson.items(f, 'documents.item')
        for doc in parser:
            yield doc


def load_metadata_from_json(filename: str) -> Tuple[Dict, Dict, int]:
    """
    Загружает только metadata (mappings, settings) из JSON файла экспорта.
    Для больших файлов пытается извлечь только metadata без загрузки документов.
    
    Args:
        filename: Путь к JSON файлу
        
    Returns:
        Кортеж (mappings, settings, total_docs)
        total_docs будет 0 для больших файлов
    """
    mappings = {}
    settings = {}
    total_docs = 0
    
    # Используем ijson для извлечения только mappings и settings
    if HAS_IJSON:
        try:
            with open(filename, 'rb') as f:
                # Парсим mappings
                try:
                    parser = ijson.items(f, 'mappings')
                    mappings = next(parser, {})
                except:
                    pass
                
                f.seek(0)
                # Парсим settings
                try:
                    parser = ijson.items(f, 'settings')
                    settings = next(parser, {})
                except:
                    pass
        except Exception as e:
            print(f"   ⚠️  Ошибка чтения metadata через ijson: {e}")
    
    # Если ijson не сработал, попробуем частичное чтение файла
    if not mappings and not settings:
        try:
            # Читаем первые мегабайты файла, где обычно находятся mappings и settings
            with open(filename, 'r', encoding='utf-8') as f:
                chunk = f.read(2 * 1024 * 1024)  # 2MB должно хватить для metadata
                
                # Находим позицию начала массива documents
                documents_pos = chunk.find('"documents"')
                if documents_pos > 0:
                    # Берем только часть до documents
                    metadata_chunk = chunk[:documents_pos] + '}'
                    try:
                        partial_data = json.loads(metadata_chunk)
                        mappings = partial_data.get('mappings', {})
                        settings = partial_data.get('settings', {})
                    except:
                        pass
        except Exception as e:
            print(f"   ⚠️  Ошибка частичного чтения metadata: {e}")
    
    return mappings, settings, total_docs


def import_index(client: OpenSearch, index_name: str, export_dir: str, overwrite: bool = False) -> bool:
    """
    Импорт индекса в OpenSearch из JSON файла.
    
    Args:
        client: Клиент OpenSearch
        index_name: Имя индекса для импорта
        export_dir: Директория с экспортированными файлами
        overwrite: Перезаписать существующий индекс
        
    Returns:
        True если успешно, False иначе
    """
    print(f"\n{'='*60}")
    print(f"Импорт индекса: {index_name}")
    print(f"{'='*60}")
    
    filename = os.path.join(export_dir, f'{index_name}_export.json')
    
    if not os.path.exists(filename):
        print(f"⚠️  Файл {filename} не найден, пропускаем")
        return False
    
    try:
        # Проверяем размер файла
        print(f"📂 Загрузка данных из файла: {filename}")
        file_size_mb = os.path.getsize(filename) / (1024 * 1024)
        print(f"   Размер файла: {file_size_mb:.2f} MB")
        
        # Определяем, нужно ли использовать потоковое чтение
        use_streaming = file_size_mb > STREAMING_THRESHOLD_MB
        
        if use_streaming:
            if not HAS_IJSON:
                print(f"   ❌ Файл слишком большой ({file_size_mb:.2f} MB), требуется ijson для потокового чтения")
                print(f"   Установите: pip install ijson")
                return False
            
            print(f"   ⚠️  Большой файл. Используется потоковое чтение (не загружает весь файл в память)")
            
            # Загружаем только metadata
            mapping, settings, total_docs = load_metadata_from_json(filename)
            if total_docs == 0:
                print(f"   ⚠️  Не удалось определить количество документов, будет подсчитано во время импорта")
            else:
                print(f"   Документов в файле: {total_docs}")
            
            documents = None  # Будем читать потоково
        else:
            # Загружаем весь файл для маленьких файлов
            print(f"   Загрузка файла в память...")
            with open(filename, 'r', encoding='utf-8') as f:
                export_data = json.load(f)
            
            mapping = export_data.get('mappings', {})
            settings = export_data.get('settings', {})
            documents = export_data.get('documents', [])
            total_docs = len(documents)
            print(f"   Загружено в память: {total_docs} документов")
        
        # Проверка существования индекса
        if client.indices.exists(index=index_name):
            if overwrite:
                print(f"🗑️  Удаление существующего индекса...")
                client.indices.delete(index=index_name)
            else:
                print(f"⚠️  Индекс {index_name} уже существует. Используйте overwrite=True для перезаписи")
                return False
        
        # Создание индекса с mapping и settings
        print(f"📋 Создание индекса с mapping...")
        index_body = {}
        
        if mapping:
            index_body['mappings'] = mapping
        
        if settings:
            # Settings могут быть вложены в 'index' ключ
            # Очищаем settings от служебных полей и несовместимых настроек
            def clean_settings_recursive(settings_dict, path=""):
                """
                Рекурсивно очищает настройки от служебных и несовместимых полей.
                
                Args:
                    settings_dict: Словарь с настройками
                    path: Текущий путь к настройке (для логирования)
                    
                Returns:
                    Очищенный словарь настроек
                """
                if not isinstance(settings_dict, dict):
                    return settings_dict
                
                cleaned = {}
                for key, value in settings_dict.items():
                    current_path = f"{path}.{key}" if path else key
                    
                    # Пропускаем служебные поля, которые нельзя установить при создании
                    if key in ['uuid', 'version', 'creation_date', 'provided_name']:
                        print(f"   ⚠️  Пропущена служебная настройка: {current_path}")
                        continue
                    
                    # Пропускаем несовместимые настройки KNN derived_source
                    # Это настройка, которая не поддерживается в OpenSearch 2.11.0
                    if key == 'derived_source' and 'knn' in path.lower():
                        print(f"   ⚠️  Пропущена несовместимая настройка KNN: {current_path}")
                        continue
                    
                    # Если значение - словарь, рекурсивно очищаем его
                    if isinstance(value, dict):
                        cleaned_value = clean_settings_recursive(value, current_path)
                        if cleaned_value:  # Добавляем только если что-то осталось
                            cleaned[key] = cleaned_value
                    else:
                        # Для простых значений добавляем как есть
                        cleaned[key] = value
                
                return cleaned
            
            # Если settings имеет структуру {'index': {...}}, извлекаем внутренние настройки
            if 'index' in settings and isinstance(settings['index'], dict):
                index_settings = settings['index']
                clean_settings = clean_settings_recursive(index_settings, 'index')
                # Обернем обратно в 'index'
                if clean_settings:
                    index_body['settings'] = {'index': clean_settings}
                    print(f"   ✓ Настроек применено: {len(clean_settings)}")
                else:
                    print(f"   ⚠️  Все настройки были отфильтрованы, используем только mappings")
            else:
                # Иначе используем settings как есть, но очищаем служебные поля
                clean_settings = clean_settings_recursive(settings)
                if clean_settings:
                    index_body['settings'] = clean_settings
                    print(f"   ✓ Настроек применено: {len(clean_settings)}")
                else:
                    print(f"   ⚠️  Все настройки были отфильтрованы, используем только mappings")
        
        # Используем body параметр для совместимости со старыми версиями API
        try:
            try:
                client.indices.create(index=index_name, body=index_body)
            except TypeError:
                # Для новых версий opensearch-py может потребоваться передавать напрямую
                client.indices.create(index=index_name, **index_body)
            print(f"✓ Индекс создан")
        except Exception as create_error:
            # Если ошибка связана с несовместимыми настройками, попробуем создать без settings
            error_msg = str(create_error).lower()
            if 'unknown setting' in error_msg or 'illegal_argument' in error_msg:
                print(f"   ⚠️  Ошибка создания с settings: {create_error}")
                print(f"   🔄 Попытка создать индекс только с mappings (без settings)...")
                # Создаем только с mappings, без settings
                index_body_minimal = {'mappings': index_body.get('mappings', {})}
                try:
                    try:
                        client.indices.create(index=index_name, body=index_body_minimal)
                    except TypeError:
                        client.indices.create(index=index_name, **index_body_minimal)
                    print(f"✓ Индекс создан только с mappings (settings отброшены из-за несовместимости)")
                except Exception as minimal_error:
                    print(f"❌ Ошибка создания индекса даже без settings: {minimal_error}")
                    raise
            else:
                raise
        
        # Импорт документов через bulk API
        if documents is not None or use_streaming:
            print(f"📦 Импорт документов...")
            actions = []
            total_successful = 0
            total_failed = 0
            processed_count = 0
            
            # Определяем источник документов
            if use_streaming:
                # Потоковое чтение для больших файлов
                doc_iter = stream_documents_from_json(filename)
            else:
                # Обычное чтение из списка
                doc_iter = documents
            
            for doc in doc_iter:
                # Извлекаем _id и _source из структуры экспорта
                if isinstance(doc, dict) and '_id' in doc and '_source' in doc:
                    # Структура экспорта: {"_id": "...", "_source": {...}}
                    doc_id = doc['_id']
                    doc_source = doc['_source']
                else:
                    # Если структура другая, используем doc как есть
                    doc_id = doc.get('_id') or doc.get('id')
                    doc_source = doc
                
                action = {
                    '_index': index_name,
                    '_id': doc_id,
                    '_source': doc_source
                }
                actions.append(action)
                processed_count += 1
                
                # Выполняем bulk insert батчами
                if len(actions) >= BATCH_SIZE:
                    try:
                        # bulk возвращает кортеж (success_count, failed_items)
                        success_count, failed_items = bulk(
                            client, 
                            actions, 
                            chunk_size=BATCH_SIZE,
                            refresh=False  # Не обновляем после каждого батча для скорости
                        )
                        total_successful += success_count
                        if failed_items:
                            total_failed += len(failed_items)
                            print(f"   ⚠️  Ошибок в батче: {len(failed_items)}")
                    except Exception as bulk_error:
                        print(f"   ❌ Ошибка bulk insert: {bulk_error}")
                        total_failed += len(actions)
                    actions = []
                    # Выводим прогресс каждые BATCH_SIZE документов
                    if total_docs > 0:
                        if processed_count % BATCH_SIZE == 0 or processed_count == total_docs:
                            print(f"   Прогресс: {processed_count}/{total_docs} (успешно: {total_successful}, ошибок: {total_failed})")
                    else:
                        if processed_count % BATCH_SIZE == 0:
                            print(f"   Обработано: {processed_count} (успешно: {total_successful}, ошибок: {total_failed})")
            
            # Импорт оставшихся документов
            if actions:
                try:
                    success_count, failed_items = bulk(
                        client, 
                        actions, 
                        chunk_size=BATCH_SIZE,
                        refresh=False
                    )
                    total_successful += success_count
                    if failed_items:
                        total_failed += len(failed_items)
                        print(f"   ⚠️  Ошибок в последнем батче: {len(failed_items)}")
                except Exception as bulk_error:
                    print(f"   ❌ Ошибка bulk insert последнего батча: {bulk_error}")
                    total_failed += len(actions)
            
            # Обновляем индекс после импорта всех документов
            print(f"   🔄 Обновление индекса...")
            try:
                client.indices.refresh(index=index_name)
            except Exception as refresh_error:
                print(f"   ⚠️  Ошибка обновления индекса: {refresh_error}")
            
            # Обновляем total_docs если не было известно заранее
            if total_docs == 0:
                total_docs = processed_count
            
            print(f"✓ Импорт завершен. Обработано: {processed_count}, Успешно: {total_successful}, Ошибок: {total_failed}")
        
        # Проверка количества документов в индексе
        print(f"   📊 Подсчет документов в индексе...")
        try:
            count_response = client.count(index=index_name)
            imported_count = count_response['count']
            print(f"✓ Документов в индексе: {imported_count}")
            
            if total_docs > 0 and imported_count != total_docs:
                print(f"⚠️  Внимание: В индексе {imported_count} документов, ожидалось {total_docs}")
        except Exception as count_error:
            print(f"⚠️  Ошибка подсчета документов: {count_error}")
            imported_count = 0
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка импорта индекса {index_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция импорта."""
    print("="*60)
    print("ИМПОРТ ИНДЕКСОВ OPENSEARCH")
    print("="*60)
    
    # Проверка директории экспорта
    if not os.path.exists(EXPORT_DIR):
        print(f"❌ Директория {EXPORT_DIR} не найдена")
        print(f"   Сначала выполните экспорт через export_opensearch.py")
        sys.exit(1)
    
    print(f"📁 Директория с данными: {EXPORT_DIR}")
    
    # Подключение к OpenSearch
    print(f"\n🔌 Подключение к OpenSearch...")
    print(f"   Host: {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
    print(f"   SSL: {OPENSEARCH_USE_SSL}")
    if OPENSEARCH_USERNAME:
        print(f"   Username: {OPENSEARCH_USERNAME}")
    else:
        print(f"   Authentication: disabled (без аутентификации)")
    
    try:
        # Настройка аутентификации (если указана)
        auth = None
        if OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD:
            auth = (OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
        
        client = OpenSearch(
            hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
            http_auth=auth,
            use_ssl=OPENSEARCH_USE_SSL,
            verify_certs=OPENSEARCH_VERIFY_CERTS,
            timeout=60
        )
        
        # Проверка подключения
        if not client.ping():
            print("❌ Не удалось подключиться к OpenSearch")
            sys.exit(1)
        
        print("✓ Подключение установлено")
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        sys.exit(1)
    
    # Поиск файлов экспорта
    export_files = [f for f in os.listdir(EXPORT_DIR) if f.endswith('_export.json')]
    
    if not export_files:
        print(f"❌ Файлы экспорта не найдены в {EXPORT_DIR}")
        sys.exit(1)
    
    # Извлечение имен индексов из имен файлов
    indices_to_import = [f.replace('_export.json', '') for f in export_files]
    print(f"\n📋 Найдены индексы для импорта: {', '.join(indices_to_import)}")
    
    # Подтверждение
    print(f"\n⚠️  Внимание: Существующие индексы будут перезаписаны!")
    confirm = input("Продолжить? (yes/no): ")
    if confirm.lower() not in ['yes', 'y']:
        print("Отменено")
        sys.exit(0)
    
    # Импорт каждого индекса
    results = {}
    for index_name in indices_to_import:
        success = import_index(client, index_name, EXPORT_DIR, overwrite=True)
        results[index_name] = success
    
    # Итоговая статистика
    print(f"\n{'='*60}")
    print("ИТОГИ ИМПОРТА")
    print(f"{'='*60}")
    
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    for index_name, success in results.items():
        status = "✓ Успешно" if success else "❌ Ошибка"
        print(f"  {index_name}: {status}")
    
    print(f"\nУспешно импортировано: {successful}/{total}")
    
    if successful > 0:
        print(f"\n✓ Импорт завершен успешно!")
        print(f"\nСледующий шаг: Обновите конфигурацию приложения на Beget")


if __name__ == "__main__":
    main()

