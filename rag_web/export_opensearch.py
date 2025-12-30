#!/usr/bin/env python3
"""
Скрипт для экспорта индексов из локального OpenSearch.
Используйте этот скрипт перед миграцией на новый сервер OpenSearch.

Использование:
    python export_opensearch.py
"""

import json
import sys
import os
from opensearchpy import OpenSearch
from typing import List, Dict, Any

# Конфигурация локального OpenSearch
OPENSEARCH_HOST = os.environ.get('OPENSEARCH_HOST', 'localhost')
OPENSEARCH_PORT = int(os.environ.get('OPENSEARCH_PORT', 9200))
OPENSEARCH_USE_SSL = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'
OPENSEARCH_VERIFY_CERTS = os.environ.get('OPENSEARCH_VERIFY_CERTS', 'False').lower() == 'true'
# Настройка аутентификации
OPENSEARCH_USERNAME = os.environ.get('OPENSEARCH_USERNAME') or os.environ.get('OPENSEARCH_AUTH_USERNAME')
OPENSEARCH_PASSWORD = os.environ.get('OPENSEARCH_PASSWORD') or os.environ.get('OPENSEARCH_AUTH_PASSWORD')

# Индексы для экспорта
INDICES_TO_EXPORT = ['rag_descriptions', 'rag_layers']

# Директория для экспорта
EXPORT_DIR = 'opensearch_export'


def export_index(client: OpenSearch, index_name: str, export_dir: str) -> bool:
    """
    Экспорт индекса из OpenSearch в JSON файл.
    
    Args:
        client: Клиент OpenSearch
        index_name: Имя индекса для экспорта
        export_dir: Директория для сохранения файлов
        
    Returns:
        True если успешно, False иначе
    """
    print(f"\n{'='*60}")
    print(f"Экспорт индекса: {index_name}")
    print(f"{'='*60}")
    
    try:
        # Проверка существования индекса
        if not client.indices.exists(index=index_name):
            print(f"⚠️  Индекс {index_name} не существует, пропускаем")
            return False
        
        # Получаем mapping индекса
        print(f"📋 Получение mapping индекса...")
        mapping_response = client.indices.get_mapping(index=index_name)
        mapping = mapping_response.get(index_name, {}).get('mappings', {})
        
        # Получаем settings индекса
        print(f"⚙️  Получение settings индекса...")
        settings_response = client.indices.get_settings(index=index_name)
        settings = settings_response.get(index_name, {}).get('settings', {})
        
        # Получаем все документы через scroll API
        print(f"📦 Получение документов...")
        all_docs = []
        scroll_size = 1000
        
        # Начальный запрос
        response = client.search(
            index=index_name,
            body={"query": {"match_all": {}}},
            scroll='5m',
            size=scroll_size
        )
        
        scroll_id = response.get('_scroll_id')
        hits = response['hits']['hits']
        total_hits = response['hits']['total']
        
        # Обработка total (может быть int или dict с value)
        if isinstance(total_hits, dict):
            total_count = total_hits.get('value', 0)
        else:
            total_count = total_hits
        
        print(f"   Всего документов: {total_count}")
        
        # Обработка первой партии
        for hit in hits:
            all_docs.append({
                '_id': hit['_id'],
                '_source': hit['_source']
            })
        
        processed = len(hits)
        print(f"   Загружено: {processed}/{total_count}")
        
        # Продолжаем scroll пока есть результаты
        while len(hits) > 0:
            response = client.scroll(
                scroll_id=scroll_id,
                scroll='5m'
            )
            
            scroll_id = response.get('_scroll_id')
            hits = response['hits']['hits']
            
            for hit in hits:
                all_docs.append({
                    '_id': hit['_id'],
                    '_source': hit['_source']
                })
            
            processed += len(hits)
            if processed % 1000 == 0:
                print(f"   Загружено: {processed}/{total_count}")
        
        # Очистка scroll контекста
        if scroll_id:
            try:
                client.clear_scroll(scroll_id=scroll_id)
            except:
                pass
        
        print(f"✓ Загружено документов: {len(all_docs)}")
        
        # Сохраняем данные в файл
        export_data = {
            'index_name': index_name,
            'mappings': mapping,
            'settings': settings,
            'documents': all_docs,
            'total_documents': len(all_docs)
        }
        
        filename = os.path.join(export_dir, f'{index_name}_export.json')
        print(f"💾 Сохранение в файл: {filename}")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
        print(f"✓ Файл сохранен: {file_size:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка экспорта индекса {index_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Основная функция экспорта."""
    print("="*60)
    print("ЭКСПОРТ ИНДЕКСОВ OPENSEARCH")
    print("="*60)
    
    # Создаем директорию для экспорта
    os.makedirs(EXPORT_DIR, exist_ok=True)
    print(f"📁 Директория экспорта: {EXPORT_DIR}")
    
    # Подключение к OpenSearch
    print(f"\n🔌 Подключение к OpenSearch...")
    print(f"   Host: {OPENSEARCH_HOST}:{OPENSEARCH_PORT}")
    print(f"   SSL: {OPENSEARCH_USE_SSL}")
    if OPENSEARCH_USERNAME:
        print(f"   Username: {OPENSEARCH_USERNAME}")
    else:
        print(f"   Authentication: disabled")
    
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
    
    # Экспорт каждого индекса
    results = {}
    for index_name in INDICES_TO_EXPORT:
        success = export_index(client, index_name, EXPORT_DIR)
        results[index_name] = success
    
    # Итоговая статистика
    print(f"\n{'='*60}")
    print("ИТОГИ ЭКСПОРТА")
    print(f"{'='*60}")
    
    successful = sum(1 for v in results.values() if v)
    total = len(results)
    
    for index_name, success in results.items():
        status = "✓ Успешно" if success else "❌ Ошибка"
        print(f"  {index_name}: {status}")
    
    print(f"\nУспешно экспортировано: {successful}/{total}")
    
    if successful > 0:
        print(f"\n📁 Файлы сохранены в: {EXPORT_DIR}/")
        print(f"\nСледующий шаг: Используйте import_opensearch.py для импорта на новый сервер")


if __name__ == "__main__":
    main()

