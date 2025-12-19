"""
Простой пример использования RAG системы.

Этот скрипт демонстрирует базовое использование RAG системы без OpenSearch.
"""

from rag_system import RAGSystem
from opensearch_test import GIGACHAT_CREDENTIALS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Основная функция для демонстрации работы RAG системы."""
    
    # Путь к CSV файлу с данными
    CSV_PATH = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/parsed_layers.csv"
    
    logger.info("="*80)
    logger.info("ИНИЦИАЛИЗАЦИЯ RAG СИСТЕМЫ")
    logger.info("="*80)
    
    # Инициализация RAG системы БЕЗ OpenSearch (проще для начала)
    # Если у вас настроен OpenSearch, раскомментируйте код ниже
    rag_system = RAGSystem(
        csv_path=CSV_PATH,
        use_opensearch=False,  # Используем только SQL запросы
        credentials=GIGACHAT_CREDENTIALS
    )
    
    # Если у вас настроен OpenSearch, используйте это:
    """
    OPENSEARCH_CONFIG = {
        'host': "localhost",
        'port': 9200,
        'use_ssl': False,
        'verify_certs': False,
        'http_auth': ("admin", "Rodion1killer"),
        'embedding_model': "ai-forever/sbert_large_nlu_ru"
    }
    
    rag_system = RAGSystem(
        csv_path=CSV_PATH,
        opensearch_config=OPENSEARCH_CONFIG,
        opensearch_index="rag_neft",
        use_opensearch=True,
        credentials=GIGACHAT_CREDENTIALS
    )
    """
    
    logger.info("RAG система инициализирована успешно!\n")
    
    # Примеры запросов
    test_queries = [
        # Структурированные запросы (SQL)
        "Где R0 > 1.0% (зрелая нефть)?",
        "Найди максимальное значение Сорг в регионе Южный Каспий",
        
        # Семантические запросы (векторный поиск, если OpenSearch включен)
        # "Расскажи о геологических слоях Каспийского моря",
        # "Что такое R0 и зачем оно нужно?",
    ]
    
    # Выполнение запросов
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*80}")
        logger.info(f"ЗАПРОС {i}/{len(test_queries)}: {query}")
        logger.info(f"{'='*80}\n")
        
        try:
            # Выполнение запроса
            results, answer = rag_system.query(
                user_query=query,
                use_vector_search=False,  # Отключено, т.к. OpenSearch не используется
                use_sql_search=True,
                format_output=True
            )
            
            # Вывод ответа
            if answer:
                print("\n" + "="*80)
                print("ОТВЕТ:")
                print("="*80)
                print(answer)
                print("="*80 + "\n")
            
            # Вывод статистики
            if not results.empty:
                print(f"📊 Найдено результатов: {len(results)}")
                print(f"📋 Колонки в результатах: {len(results.columns)}")
                if len(results) > 0:
                    print(f"\nПервые несколько строк:")
                    print(results.head(3).to_string())
            else:
                print("❌ Результаты не найдены.")
            
            print("\n" + "-"*80 + "\n")
                
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса '{query}': {e}", exc_info=True)
            print(f"\n❌ Ошибка: {e}\n")
    
    logger.info("Все запросы обработаны!")


if __name__ == "__main__":
    main()

