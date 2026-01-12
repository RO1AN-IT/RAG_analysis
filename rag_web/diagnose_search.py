#!/usr/bin/env python3
"""
Диагностический скрипт для проверки поиска в OpenSearch.
Проверяет структуру индекса, наличие документов и тестирует поиск.
"""

import json
import os
import sys
from opensearchpy import OpenSearch
from sentence_transformers import SentenceTransformer

# Конфигурация
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '155.212.186.244')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', None)
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', None)

INDEX_NAME = 'feature_descriptions'
EMBEDDING_MODEL = "ai-forever/sbert_large_nlu_ru"

def main():
    print("="*80)
    print("ДИАГНОСТИКА ПОИСКА В OPENSEARCH")
    print("="*80)
    
    # Подключение
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
    
    if not client.ping():
        print("❌ Не удалось подключиться")
        sys.exit(1)
    
    print("✓ Подключение установлено\n")
    
    # 1. Проверка существования индекса
    print("1. ПРОВЕРКА ИНДЕКСА")
    print("-" * 80)
    if not client.indices.exists(index=INDEX_NAME):
        print(f"❌ Индекс '{INDEX_NAME}' не существует!")
        sys.exit(1)
    print(f"✓ Индекс существует\n")
    
    # 2. Проверка количества документов
    print("2. КОЛИЧЕСТВО ДОКУМЕНТОВ")
    print("-" * 80)
    count_response = client.count(index=INDEX_NAME)
    doc_count = count_response['count']
    print(f"Документов в индексе: {doc_count}")
    if doc_count == 0:
        print("❌ Индекс пуст! Нужно импортировать документы.")
        sys.exit(1)
    print()
    
    # 3. Проверка mapping
    print("3. СТРУКТУРА ИНДЕКСА (MAPPING)")
    print("-" * 80)
    mapping = client.indices.get_mapping(index=INDEX_NAME)
    index_mapping = mapping.get(INDEX_NAME, {}).get('mappings', {}).get('properties', {})
    
    vector_field = None
    text_field = None
    
    for field_name, field_props in index_mapping.items():
        field_type = field_props.get('type', 'unknown')
        print(f"  {field_name}: {field_type}")
        
        if field_type == 'knn_vector':
            vector_field = field_name
            dim = field_props.get('dimension', 'не указана')
            method = field_props.get('method', {})
            space_type = method.get('space_type', 'не указан')
            print(f"    - dimension: {dim}")
            print(f"    - space_type: {space_type}")
            print(f"    - method: {method}")
        elif field_type == 'text':
            text_field = field_name
    
    if not vector_field:
        print("❌ Поле типа knn_vector не найдено!")
        sys.exit(1)
    if not text_field:
        print("❌ Поле типа text не найдено!")
        sys.exit(1)
    
    print(f"\n✓ Векторное поле: {vector_field}")
    print(f"✓ Текстовое поле: {text_field}\n")
    
    # 4. Проверка первого документа
    print("4. ПРОВЕРКА ПЕРВОГО ДОКУМЕНТА")
    print("-" * 80)
    response = client.search(
        index=INDEX_NAME,
        body={"size": 1, "query": {"match_all": {}}}
    )
    
    if response['hits']['hits']:
        first_hit = response['hits']['hits'][0]
        source = first_hit['_source']
        
        print(f"ID: {first_hit['_id']}")
        print(f"Поля в документе:")
        for key in source.keys():
            if key == vector_field:
                vec_len = len(source[key]) if isinstance(source[key], list) else 'N/A'
                print(f"  - {key}: list длиной {vec_len}")
            else:
                value_preview = str(source[key])[:60] if source[key] else 'None'
                print(f"  - {key}: {value_preview}...")
    print()
    
    # 5. Тестовый поиск
    print("5. ТЕСТОВЫЙ ПОИСК")
    print("-" * 80)
    
    # Загружаем модель эмбеддингов
    print(f"Загрузка модели: {EMBEDDING_MODEL}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    
    # Генерируем тестовый эмбеддинг
    test_query = "PWD давление"
    print(f"Тестовый запрос: '{test_query}'")
    query_embedding = embedding_model.encode(test_query).tolist()
    print(f"Размерность эмбеддинга: {len(query_embedding)}\n")
    
    # Тест 1: Формат с knn внутри query
    print("Тест 1: Формат с knn внутри query")
    print("-" * 40)
    try:
        knn_query_v2 = {
            "size": 5,
            "query": {
                "knn": {
                    vector_field: {
                        "vector": query_embedding,
                        "k": 5
                    }
                }
            }
        }
        
        response = client.search(index=INDEX_NAME, body=knn_query_v2)
        hits_count = len(response['hits']['hits'])
        print(f"✓ Запрос выполнен успешно")
        print(f"  Найдено документов: {hits_count}")
        
        if hits_count > 0:
            print(f"  Первый результат:")
            first_hit = response['hits']['hits'][0]
            print(f"    ID: {first_hit['_id']}")
            print(f"    Score: {first_hit['_score']}")
            text_preview = first_hit['_source'].get(text_field, '')[:100]
            print(f"    Text: {text_preview}...")
        else:
            print("  ⚠️  НО: 0 результатов!")
            print("  Проверяем детали ответа...")
            print(f"  Total: {response['hits']['total']}")
            print(f"  Max score: {response['hits']['max_score']}")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    
    print()
    
    # Тест 2: Формат с knn на верхнем уровне (если поддерживается)
    print("Тест 2: Формат с knn на верхнем уровне")
    print("-" * 40)
    try:
        knn_query_v1 = {
            "size": 5,
            "knn": {
                vector_field: {
                    "vector": query_embedding,
                    "k": 5
                }
            }
        }
        
        response = client.search(index=INDEX_NAME, body=knn_query_v1)
        hits_count = len(response['hits']['hits'])
        print(f"✓ Запрос выполнен успешно")
        print(f"  Найдено документов: {hits_count}")
    except Exception as e:
        print(f"⚠️  Не поддерживается: {e}")
    
    print()
    
    # Тест 3: Поиск с фильтром по space_type
    print("Тест 3: Проверка space_type в запросе")
    print("-" * 40)
    try:
        # Для cosinesimil может потребоваться нормализация вектора
        import numpy as np
        query_vec = np.array(query_embedding)
        # Нормализуем для cosine similarity
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            normalized_embedding = (query_vec / norm).tolist()
        else:
            normalized_embedding = query_embedding
        
        knn_query_normalized = {
            "size": 5,
            "query": {
                "knn": {
                    vector_field: {
                        "vector": normalized_embedding,
                        "k": 5
                    }
                }
            }
        }
        
        response = client.search(index=INDEX_NAME, body=knn_query_normalized)
        hits_count = len(response['hits']['hits'])
        print(f"✓ Запрос с нормализованным вектором выполнен")
        print(f"  Найдено документов: {hits_count}")
    except Exception as e:
        print(f"⚠️  Ошибка: {e}")
    
    print()
    print("="*80)
    print("ДИАГНОСТИКА ЗАВЕРШЕНА")
    print("="*80)

if __name__ == "__main__":
    main()

