#!/usr/bin/env python3
"""
Скрипт для просмотра первых документов из индекса OpenSearch.

Использование:
    python view_opensearch_docs.py [index_name] [count]
    
Примеры:
    python view_opensearch_docs.py                    # Покажет все индексы
    python view_opensearch_docs.py rag_layers        # Первые 5 документов из rag_layers
    python view_opensearch_docs.py rag_layers 10     # Первые 10 документов
"""

import json
import sys
import os
from opensearchpy import OpenSearch

# Конфигурация OpenSearch (та же, что в import_opensearch.py)
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', '155.212.186.244')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME', None)
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD', None)


def get_opensearch_client():
    """Создает и возвращает клиент OpenSearch."""
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
    
    return client


def list_indices(client):
    """Выводит список всех индексов."""
    try:
        indices = client.indices.get_alias()
        print("="*60)
        print("ДОСТУПНЫЕ ИНДЕКСЫ")
        print("="*60)
        for index_name in sorted(indices.keys()):
            # Получаем количество документов
            try:
                count = client.count(index=index_name)['count']
                print(f"  {index_name}: {count} документов")
            except:
                print(f"  {index_name}")
        print()
    except Exception as e:
        print(f"❌ Ошибка при получении списка индексов: {e}")


def view_documents(client, index_name, count=5):
    """Выводит первые документы из указанного индекса."""
    print("="*60)
    print(f"ДОКУМЕНТЫ ИЗ ИНДЕКСА: {index_name}")
    print("="*60)
    
    try:
        # Проверка существования индекса
        if not client.indices.exists(index=index_name):
            print(f"❌ Индекс '{index_name}' не существует")
            return
        
        # Получаем общее количество документов
        total_count = client.count(index=index_name)['count']
        print(f"Всего документов в индексе: {total_count}\n")
        
        if total_count == 0:
            print("⚠️  Индекс пуст")
            return
        
        # Получаем первые документы
        response = client.search(
            index=index_name,
            body={
                "size": count,
                "query": {
                    "match_all": {}
                }
            }
        )
        
        hits = response.get('hits', {}).get('hits', [])
        
        if not hits:
            print("⚠️  Документы не найдены")
            return
        
        print(f"Показано документов: {len(hits)} из {total_count}\n")
        
        for i, hit in enumerate(hits, 1):
            doc_id = hit.get('_id', 'N/A')
            source = hit.get('_source', {})
            
            print(f"{'='*60}")
            print(f"ДОКУМЕНТ #{i}")
            print(f"{'='*60}")
            print(f"ID: {doc_id}")
            print(f"Score: {hit.get('_score', 'N/A')}")
            print(f"\nСодержимое:")
            print(json.dumps(source, ensure_ascii=False, indent=2))
            print()
        
    except Exception as e:
        print(f"❌ Ошибка при получении документов: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Основная функция."""
    # Получаем параметры из командной строки
    index_name = None
    count = 5
    
    if len(sys.argv) > 1:
        index_name = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            count = int(sys.argv[2])
        except ValueError:
            print(f"⚠️  Неверное значение count: {sys.argv[2]}, используется значение по умолчанию: 5")
            count = 5
    
    # Подключение к OpenSearch
    print("🔌 Подключение к OpenSearch...")
    print(f"   Host: {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
    
    try:
        client = get_opensearch_client()
        
        if not client.ping():
            print("❌ Не удалось подключиться к OpenSearch")
            sys.exit(1)
        
        print("✓ Подключение установлено\n")
        
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        sys.exit(1)
    
    # Если индекс не указан, показываем список индексов
    if not index_name:
        list_indices(client)
        print("Использование:")
        print("  python view_opensearch_docs.py <index_name> [count]")
        print("\nПример:")
        print("  python view_opensearch_docs.py rag_layers 5")
    else:
        # Показываем документы из указанного индекса
        view_documents(client, index_name, count)


if __name__ == "__main__":
    main()

