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
from typing import List, Dict, Any

# Конфигурация нового OpenSearch
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '155.212.186.244')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', None)
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', None)

# Директория с экспортированными данными
EXPORT_DIR = 'opensearch_export'

# Размер батча для bulk insert
BATCH_SIZE = 500


def clean_settings_recursive(settings_dict: dict, excluded_keys: set) -> dict:
    """
    Рекурсивно очищает настройки от исключенных ключей.
    
    Args:
        settings_dict: Словарь с настройками
        excluded_keys: Множество ключей для исключения
        
    Returns:
        Очищенный словарь настроек
    """
    cleaned = {}
    for key, value in settings_dict.items():
        # Пропускаем исключенные ключи
        if key in excluded_keys:
            continue
        
        # Если значение - словарь, рекурсивно очищаем его
        if isinstance(value, dict):
            cleaned_value = clean_settings_recursive(value, excluded_keys)
            # Добавляем только если словарь не пустой
            if cleaned_value:
                cleaned[key] = cleaned_value
        else:
            cleaned[key] = value
    
    return cleaned


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
        # Загружаем данные из файла
        print(f"📂 Загрузка данных из файла: {filename}")
        with open(filename, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        mapping = export_data.get('mappings', {})
        settings = export_data.get('settings', {})
        documents = export_data.get('documents', [])
        total_docs = len(documents)
        
        print(f"   Документов в файле: {total_docs}")
        
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
            
            # Проверяем, есть ли поле knn_vector в mapping - нужно включить KNN
            if 'properties' in mapping:
                has_knn_vector = any(
                    prop.get('type') == 'knn_vector' 
                    for prop in mapping['properties'].values()
                )
                if has_knn_vector:
                    print(f"   ⚠️  Обнаружено поле knn_vector - будет включен KNN")
        
        if settings:
            # Settings могут быть вложены в 'index' ключ
            # Очищаем settings от служебных полей, которые нельзя установить при создании
            
            # Список настроек, которые нужно исключить (служебные или несовместимые)
            excluded_settings = {
                'uuid', 'version', 'creation_date', 'provided_name',
                # KNN настройки, которые могут требовать плагины или не поддерживаться
                'knn.derived_source',  # Настройка на верхнем уровне index
                'derived_source',  # Исключаем весь блок derived_source внутри knn
            }
            
            # Если settings имеет структуру {'index': {...}}, извлекаем внутренние настройки
            if 'index' in settings and isinstance(settings['index'], dict):
                index_settings = settings['index']
                # Рекурсивно очищаем настройки
                clean_settings = clean_settings_recursive(index_settings, excluded_settings)
                
                # Дополнительно удаляем knn.derived_source (может быть на верхнем уровне как 'knn.derived_source')
                if 'knn.derived_source' in clean_settings:
                    del clean_settings['knn.derived_source']
                    print(f"   ⚠️  Исключена несовместимая настройка: knn.derived_source")
                
                # Дополнительно удаляем весь блок knn, если он содержит несовместимые настройки
                if 'knn' in clean_settings:
                    knn_settings = clean_settings['knn']
                    if isinstance(knn_settings, dict):
                        # Удаляем derived_source из knn, если он есть
                        if 'derived_source' in knn_settings:
                            del knn_settings['derived_source']
                        # Если knn стал пустым, удаляем его полностью
                        if not knn_settings:
                            del clean_settings['knn']
                
                # Проверяем, нужно ли включить KNN (если есть knn_vector в mapping и не установлено в settings)
                if mapping and 'properties' in mapping:
                    has_knn_vector = any(
                        prop.get('type') == 'knn_vector' 
                        for prop in mapping['properties'].values()
                    )
                    if has_knn_vector and 'knn' not in clean_settings:
                        # Включаем KNN для индекса (index.knn = true)
                        clean_settings['knn'] = True
                        print(f"   ✓ Включена настройка KNN для индекса (index.knn = true)")
                
                # Обернем обратно в 'index'
                if clean_settings:
                    index_body['settings'] = {'index': clean_settings}
            else:
                # Иначе используем settings как есть, но очищаем служебные поля
                clean_settings = clean_settings_recursive(settings, excluded_settings)
                
                # Дополнительно удаляем knn.derived_source (может быть на верхнем уровне как 'knn.derived_source')
                if 'knn.derived_source' in clean_settings:
                    del clean_settings['knn.derived_source']
                    print(f"   ⚠️  Исключена несовместимая настройка: knn.derived_source")
                
                # Дополнительно удаляем knn.derived_source, если он есть
                if 'knn' in clean_settings and isinstance(clean_settings['knn'], dict):
                    if 'derived_source' in clean_settings['knn']:
                        del clean_settings['knn']['derived_source']
                    if not clean_settings['knn']:
                        del clean_settings['knn']
                
                # Проверяем, нужно ли включить KNN (если есть knn_vector в mapping)
                if mapping and 'properties' in mapping:
                    has_knn_vector = any(
                        prop.get('type') == 'knn_vector' 
                        for prop in mapping['properties'].values()
                    )
                    if has_knn_vector:
                        # Для неструктурированных settings добавляем в корень
                        if 'index' not in clean_settings:
                            clean_settings['index'] = {}
                        if isinstance(clean_settings.get('index'), dict) and 'knn' not in clean_settings['index']:
                            clean_settings['index']['knn'] = True
                            print(f"   ✓ Включена настройка KNN для индекса (index.knn = true)")
                
                if clean_settings:
                    index_body['settings'] = clean_settings
        
        # Используем body параметр для совместимости со старыми версиями API
        try:
            client.indices.create(index=index_name, body=index_body)
        except TypeError:
            # Для новых версий opensearch-py может потребоваться передавать напрямую
            client.indices.create(index=index_name, **index_body)
        print(f"✓ Индекс создан")
        
        # Небольшая задержка для стабилизации индекса
        import time
        time.sleep(1)
        
        # Импорт документов через bulk API
        if documents:
            print(f"📦 Импорт документов...")
            actions = []
            total_imported = 0
            total_failed = 0
            
            for i, doc in enumerate(documents):
                action = {
                    '_index': index_name,
                    '_id': doc['_id'],
                    '_source': doc['_source']
                }
                actions.append(action)
                
                # Выполняем bulk insert батчами
                if len(actions) >= BATCH_SIZE:
                    try:
                        # Используем refresh='wait_for' для последнего батча, чтобы документы были доступны сразу
                        is_last_batch = (i + 1 >= total_docs)
                        refresh_param = 'wait_for' if is_last_batch else False
                        
                        result = bulk(
                            client, 
                            actions, 
                            chunk_size=BATCH_SIZE, 
                            refresh=refresh_param,
                            request_timeout=120
                        )
                        
                        # bulk возвращает кортеж (success_count, failed_items)
                        if isinstance(result, tuple) and len(result) >= 2:
                            success_count, failed_items = result[0], result[1]
                            total_imported += success_count
                            if failed_items:
                                total_failed += len(failed_items)
                                print(f"   ⚠️  Ошибок в батче: {len(failed_items)}")
                                # Выводим первые ошибки для отладки
                                for error_item in failed_items[:3]:
                                    error_info = error_item.get('index', {}).get('error', {})
                                    if isinstance(error_info, dict):
                                        error_msg = error_info.get('reason', str(error_info))
                                    else:
                                        error_msg = str(error_info)
                                    print(f"      Ошибка: {error_msg}")
                        else:
                            # Если bulk вернул неожиданный формат, считаем что все успешно
                            print(f"   ⚠️  Неожиданный формат результата bulk: {type(result)}")
                            total_imported += len(actions)
                    except Exception as e:
                        print(f"   ❌ Ошибка при bulk insert: {e}")
                        import traceback
                        traceback.print_exc()
                        total_failed += len(actions)
                    
                    actions = []
                    print(f"   Импортировано: {i+1}/{total_docs} (успешно: {total_imported}, ошибок: {total_failed})")
            
            # Импорт оставшихся документов
            if actions:
                try:
                    # Для последнего батча используем refresh='wait_for'
                    result = bulk(
                        client, 
                        actions, 
                        chunk_size=BATCH_SIZE, 
                        refresh='wait_for',
                        request_timeout=120
                    )
                    if isinstance(result, tuple) and len(result) >= 2:
                        success_count, failed_items = result[0], result[1]
                        total_imported += success_count
                        if failed_items:
                            total_failed += len(failed_items)
                            print(f"   ⚠️  Ошибок в последнем батче: {len(failed_items)}")
                            for error_item in failed_items[:3]:
                                error_info = error_item.get('index', {}).get('error', {})
                                if isinstance(error_info, dict):
                                    error_msg = error_info.get('reason', str(error_info))
                                else:
                                    error_msg = str(error_info)
                                print(f"      Ошибка: {error_msg}")
                    else:
                        print(f"   ⚠️  Неожиданный формат результата bulk: {type(result)}")
                        total_imported += len(actions)
                except Exception as e:
                    print(f"   ❌ Ошибка при bulk insert последнего батча: {e}")
                    import traceback
                    traceback.print_exc()
                    total_failed += len(actions)
            
            # Дополнительный refresh для гарантии (если не использовали wait_for)
            if total_imported > 0:
                print(f"🔄 Финальное обновление индекса (refresh)...")
                try:
                    client.indices.refresh(index=index_name)
                    print(f"✓ Индекс обновлен")
                except Exception as e:
                    print(f"⚠️  Предупреждение: не удалось обновить индекс: {e}")
            
            print(f"✓ Импортировано документов: {total_imported} (ошибок: {total_failed})")
        
        # Проверка количества документов в индексе
        print(f"🔍 Проверка количества документов в индексе...")
        try:
            count_response = client.count(index=index_name)
            imported_count = count_response['count']
            print(f"✓ Документов в индексе: {imported_count}")
            
            if imported_count != total_docs:
                print(f"⚠️  Внимание: Импортировано {imported_count}, ожидалось {total_docs}")
                if imported_count == 0:
                    print(f"❌ Критическая ошибка: документы не попали в индекс!")
                    print(f"   Проверьте логи OpenSearch и права доступа к индексу")
        except Exception as e:
            print(f"⚠️  Ошибка при проверке количества документов: {e}")
        
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

