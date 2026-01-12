#!/usr/bin/env python3
"""
Скрипт для проверки индекса feature_descriptions в OpenSearch.
Проверяет существование, количество документов и структуру.
"""

import os
import sys
from opensearchpy import OpenSearch

# Конфигурация OpenSearch (та же, что в import_opensearch.py)
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '155.212.186.244')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', None)
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', None)

INDEX_NAME = 'feature_descriptions'

def main():
    print("="*60)
    print(f"ПРОВЕРКА ИНДЕКСА: {INDEX_NAME}")
    print("="*60)
    
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
        
        print("✓ Подключение установлено\n")
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        sys.exit(1)
    
    # Проверка существования индекса
    print(f"📋 Проверка существования индекса...")
    try:
        exists = client.indices.exists(index=INDEX_NAME)
        if not exists:
            print(f"❌ Индекс '{INDEX_NAME}' не существует!")
            print(f"\n💡 Решение: Выполните импорт индекса:")
            print(f"   python rag_web/import_opensearch.py")
            sys.exit(1)
        print(f"✓ Индекс существует\n")
    except Exception as e:
        print(f"❌ Ошибка проверки индекса: {e}")
        sys.exit(1)
    
    # Проверка количества документов
    print(f"📊 Проверка количества документов...")
    try:
        count_response = client.count(index=INDEX_NAME)
        doc_count = count_response['count']
        print(f"✓ Документов в индексе: {doc_count}")
        if doc_count == 0:
            print(f"\n⚠️  ВНИМАНИЕ: Индекс пуст!")
            print(f"💡 Решение: Выполните импорт индекса:")
            print(f"   python rag_web/import_opensearch.py")
            sys.exit(1)
        print()
    except Exception as e:
        print(f"❌ Ошибка подсчета документов: {e}")
        sys.exit(1)
    
    # Проверка mapping
    print(f"🔍 Проверка структуры индекса (mapping)...")
    try:
        mapping = client.indices.get_mapping(index=INDEX_NAME)
        index_mapping = mapping.get(INDEX_NAME, {}).get('mappings', {}).get('properties', {})
        
        print(f"✓ Найдено полей: {len(index_mapping)}")
        print(f"\nПоля индекса:")
        for field_name, field_props in sorted(index_mapping.items()):
            field_type = field_props.get('type', 'unknown')
            print(f"  - {field_name}: {field_type}")
            
            # Проверяем, есть ли поле embedding типа knn_vector
            if field_name == 'embedding' and field_type == 'knn_vector':
                print(f"    ✓ Поле embedding типа knn_vector найдено")
                dim = field_props.get('dimension', 'не указана')
                print(f"      Размерность: {dim}")
        
        # Проверяем наличие необходимых полей
        has_embedding = 'embedding' in index_mapping
        has_text = 'text' in index_mapping
        
        print(f"\nПроверка необходимых полей:")
        print(f"  - embedding (knn_vector): {'✓' if has_embedding else '❌'}")
        print(f"  - text (text): {'✓' if has_text else '❌'}")
        
        if not has_embedding or not has_text:
            print(f"\n❌ Отсутствуют необходимые поля!")
            sys.exit(1)
        print()
        
    except Exception as e:
        print(f"❌ Ошибка получения mapping: {e}")
        sys.exit(1)
    
    # Тестовый поиск
    print(f"🔎 Тестовый поиск (KNN)...")
    try:
        # Простой тестовый вектор (нулевой вектор для проверки)
        test_vector = [0.0] * 1024  # Обычная размерность для sbert_large_nlu_ru
        
        # Формируем KNN запрос
        knn_query = {
            "size": 5,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": test_vector,
                        "k": 5
                    }
                }
            }
        }
        
        response = client.search(index=INDEX_NAME, body=knn_query)
        hits_count = len(response['hits']['hits'])
        print(f"✓ Тестовый поиск выполнен")
        print(f"  Найдено документов: {hits_count}")
        
        if hits_count > 0:
            print(f"  Первый результат:")
            first_hit = response['hits']['hits'][0]
            print(f"    ID: {first_hit['_id']}")
            print(f"    Score: {first_hit['_score']}")
            source = first_hit['_source']
            text_preview = source.get('text', '')[:100] if source.get('text') else 'N/A'
            print(f"    Text (preview): {text_preview}...")
        else:
            print(f"  ⚠️  Поиск вернул 0 результатов (возможно, проблема с запросом)")
        
    except Exception as e:
        print(f"❌ Ошибка тестового поиска: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{'='*60}")
    print(f"ПРОВЕРКА ЗАВЕРШЕНА")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

