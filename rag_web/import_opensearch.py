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
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', 'localhost')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', None)
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', None)

# Директория с экспортированными данными
EXPORT_DIR = 'opensearch_export'

# Размер батча для bulk insert
BATCH_SIZE = 500


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
        
        if settings:
            # Settings могут быть вложены в 'index' ключ
            # Очищаем settings от служебных полей, которые нельзя установить при создании
            clean_settings = {}
            
            # Если settings имеет структуру {'index': {...}}, извлекаем внутренние настройки
            if 'index' in settings and isinstance(settings['index'], dict):
                index_settings = settings['index']
                for key, value in index_settings.items():
                    # Пропускаем служебные поля
                    if key in ['uuid', 'version', 'creation_date', 'provided_name']:
                        continue
                    clean_settings[key] = value
                # Обернем обратно в 'index'
                if clean_settings:
                    index_body['settings'] = {'index': clean_settings}
            else:
                # Иначе используем settings как есть, но очищаем служебные поля
                for key, value in settings.items():
                    if key in ['uuid', 'version', 'creation_date', 'provided_name']:
                        continue
                    clean_settings[key] = value
                if clean_settings:
                    index_body['settings'] = clean_settings
        
        # Используем body параметр для совместимости со старыми версиями API
        try:
            client.indices.create(index=index_name, body=index_body)
        except TypeError:
            # Для новых версий opensearch-py может потребоваться передавать напрямую
            client.indices.create(index=index_name, **index_body)
        print(f"✓ Индекс создан")
        
        # Импорт документов через bulk API
        if documents:
            print(f"📦 Импорт документов...")
            actions = []
            
            for i, doc in enumerate(documents):
                action = {
                    '_index': index_name,
                    '_id': doc['_id'],
                    '_source': doc['_source']
                }
                actions.append(action)
                
                # Выполняем bulk insert батчами
                if len(actions) >= BATCH_SIZE:
                    success, failed = bulk(client, actions, chunk_size=BATCH_SIZE)
                    if failed:
                        print(f"   ⚠️  Ошибок в батче: {len(failed)}")
                    actions = []
                    print(f"   Импортировано: {i+1}/{total_docs}")
            
            # Импорт оставшихся документов
            if actions:
                success, failed = bulk(client, actions, chunk_size=BATCH_SIZE)
                if failed:
                    print(f"   ⚠️  Ошибок в последнем батче: {len(failed)}")
            
            print(f"✓ Импортировано документов: {total_docs}")
        
        # Проверка количества документов в индексе
        count_response = client.count(index=index_name)
        imported_count = count_response['count']
        print(f"✓ Документов в индексе: {imported_count}")
        
        if imported_count != total_docs:
            print(f"⚠️  Внимание: Импортировано {imported_count}, ожидалось {total_docs}")
        
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

