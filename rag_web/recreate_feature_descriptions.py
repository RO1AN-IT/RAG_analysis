#!/usr/bin/env python3
"""
Скрипт для пересоздания индекса feature_descriptions с правильными настройками KNN.
Удаляет существующий индекс и создает новый с index.knn = true.
"""

import json
import os
import sys

# Добавляем путь к импорту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from opensearchpy import OpenSearch
    from opensearchpy.helpers import bulk
except ImportError:
    print("❌ Модуль opensearchpy не установлен")
    print("   Установите: pip install opensearch-py")
    sys.exit(1)

# Конфигурация OpenSearch (та же, что в import_opensearch.py)
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '155.212.186.244')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', None)
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', None)

INDEX_NAME = 'feature_descriptions'
EXPORT_FILE = 'opensearch_export/feature_descriptions_export.json'
BATCH_SIZE = 500

def main():
    print("="*80)
    print("ПЕРЕСОЗДАНИЕ ИНДЕКСА feature_descriptions С НАСТРОЙКОЙ KNN")
    print("="*80)
    
    # Проверка файла экспорта
    if not os.path.exists(EXPORT_FILE):
        print(f"❌ Файл экспорта не найден: {EXPORT_FILE}")
        print(f"   Сначала выполните экспорт через export_opensearch.py")
        sys.exit(1)
    
    print(f"\n📂 Загрузка данных из: {EXPORT_FILE}")
    
    # Подключение к OpenSearch
    print(f"\n🔌 Подключение к OpenSearch...")
    print(f"   Host: {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
    
    auth = None
    if OPENSEARCH_USERNAME and OPENSEARCH_PASSWORD:
        auth = (OPENSEARCH_USERNAME, OPENSEARCH_PASSWORD)
    
    try:
        client = OpenSearch(
            hosts=[{'host': OPENSEARCH_HOST, 'port': OPENSEARCH_PORT}],
            http_auth=auth,
            use_ssl=OPENSEARCH_USE_SSL,
            verify_certs=OPENSEARCH_VERIFY_CERTS,
            timeout=60
        )
        
        if not client.ping():
            print("❌ Не удалось подключиться к OpenSearch")
            sys.exit(1)
        
        print("✓ Подключение установлено")
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        sys.exit(1)
    
    # Загрузка данных из файла
    try:
        with open(EXPORT_FILE, 'r', encoding='utf-8') as f:
            export_data = json.load(f)
        
        mapping = export_data.get('mappings', {})
        settings = export_data.get('settings', {})
        documents = export_data.get('documents', [])
        total_docs = len(documents)
        
        print(f"✓ Загружено: {total_docs} документов")
        
    except Exception as e:
        print(f"❌ Ошибка загрузки файла: {e}")
        sys.exit(1)
    
    # Проверка наличия knn_vector в mapping
    has_knn_vector = False
    if mapping and 'properties' in mapping:
        for prop in mapping['properties'].values():
            if prop.get('type') == 'knn_vector':
                has_knn_vector = True
                break
    
    if not has_knn_vector:
        print("⚠️  Поле knn_vector не найдено в mapping. KNN настройка не требуется.")
    else:
        print("✓ Обнаружено поле knn_vector - будет включен KNN")
    
    # Удаление существующего индекса
    print(f"\n🗑️  Удаление существующего индекса '{INDEX_NAME}'...")
    try:
        if client.indices.exists(index=INDEX_NAME):
            client.indices.delete(index=INDEX_NAME)
            print("✓ Индекс удален")
        else:
            print("⚠️  Индекс не существует, будет создан новый")
    except Exception as e:
        print(f"❌ Ошибка удаления индекса: {e}")
        sys.exit(1)
    
    # Создание нового индекса с правильными настройками
    print(f"\n📋 Создание индекса с правильными настройками...")
    
    index_body = {}
    
    # Добавляем mapping
    if mapping:
        index_body['mappings'] = mapping
    
    # Подготовка settings
    if settings:
        # Извлекаем settings из структуры
        if 'index' in settings and isinstance(settings['index'], dict):
            index_settings = settings['index'].copy()
        else:
            index_settings = {}
        
        # Удаляем служебные поля
        for key in ['uuid', 'version', 'creation_date', 'provided_name']:
            index_settings.pop(key, None)
        
        # Удаляем несовместимые настройки
        index_settings.pop('knn.derived_source', None)
        if 'knn' in index_settings and isinstance(index_settings['knn'], dict):
            index_settings['knn'].pop('derived_source', None)
            if not index_settings['knn']:
                index_settings.pop('knn')
        
        # ВАЖНО: Включаем KNN для индекса
        if has_knn_vector:
            index_settings['knn'] = True
            print(f"   ✓ Добавлена настройка: index.knn = true")
        
        if index_settings:
            index_body['settings'] = {'index': index_settings}
    else:
        # Если settings нет, добавляем только KNN
        if has_knn_vector:
            index_body['settings'] = {'index': {'knn': True}}
            print(f"   ✓ Добавлена настройка: index.knn = true")
    
    # Создаем индекс
    try:
        client.indices.create(index=INDEX_NAME, body=index_body)
        print("✓ Индекс создан с правильными настройками")
    except Exception as e:
        print(f"❌ Ошибка создания индекса: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Проверка settings после создания
    try:
        created_settings = client.indices.get_settings(index=INDEX_NAME)
        knn_setting = created_settings[INDEX_NAME]['settings']['index'].get('knn', None)
        if knn_setting:
            print(f"   ✓ Проверка: index.knn = {knn_setting} (включен)")
        else:
            print(f"   ⚠️  Проверка: index.knn не найден в settings (может быть проблема)")
    except:
        pass
    
    # Импорт документов
    if documents:
        print(f"\n📦 Импорт {total_docs} документов...")
        actions = []
        total_imported = 0
        total_failed = 0
        
        for i, doc in enumerate(documents):
            action = {
                '_index': INDEX_NAME,
                '_id': doc['_id'],
                '_source': doc['_source']
            }
            actions.append(action)
            
            if len(actions) >= BATCH_SIZE:
                try:
                    result = bulk(
                        client, 
                        actions, 
                        chunk_size=BATCH_SIZE, 
                        refresh=False,
                        request_timeout=120
                    )
                    if isinstance(result, tuple) and len(result) >= 2:
                        success_count, failed_items = result[0], result[1]
                        total_imported += success_count
                        if failed_items:
                            total_failed += len(failed_items)
                except Exception as e:
                    print(f"   ❌ Ошибка при bulk insert: {e}")
                    total_failed += len(actions)
                
                actions = []
                if (i + 1) % 1000 == 0:
                    print(f"   Импортировано: {i+1}/{total_docs} (успешно: {total_imported}, ошибок: {total_failed})")
        
        # Импорт оставшихся документов
        if actions:
            try:
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
            except Exception as e:
                print(f"   ❌ Ошибка при bulk insert последнего батча: {e}")
                total_failed += len(actions)
        
        # Финальный refresh
        try:
            client.indices.refresh(index=INDEX_NAME)
        except:
            pass
        
        print(f"✓ Импортировано документов: {total_imported} (ошибок: {total_failed})")
    
    # Проверка количества документов
    print(f"\n🔍 Проверка количества документов...")
    try:
        count_response = client.count(index=INDEX_NAME)
        imported_count = count_response['count']
        print(f"✓ Документов в индексе: {imported_count}")
        
        if imported_count != total_docs:
            print(f"⚠️  Внимание: Импортировано {imported_count}, ожидалось {total_docs}")
    except Exception as e:
        print(f"⚠️  Ошибка проверки: {e}")
    
    print(f"\n{'='*80}")
    print("ПЕРЕСОЗДАНИЕ ЗАВЕРШЕНО")
    print(f"{'='*80}")
    print(f"\n✓ Индекс '{INDEX_NAME}' пересоздан с правильными настройками KNN")
    print(f"✓ Попробуйте выполнить поиск снова")

if __name__ == "__main__":
    main()





