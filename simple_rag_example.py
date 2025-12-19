"""
Простой пример использования SimpleRAG для получения топ-k релевантных данных.
"""

from simple_rag import SimpleRAG
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Пример использования SimpleRAG."""
    
    # Конфигурация OpenSearch
    OPENSEARCH_HOST = "localhost"
    OPENSEARCH_PORT = 9200
    OPENSEARCH_AUTH = ("admin", "Rodion1killer")  # Замените на свои данные
    INDEX_NAME = "rag_neft"
    
    try:
        # Инициализация RAG системы
        logger.info("Инициализация RAG системы...")
        rag = SimpleRAG(
            opensearch_host=OPENSEARCH_HOST,
            opensearch_port=OPENSEARCH_PORT,
            opensearch_auth=OPENSEARCH_AUTH,
            index_name=INDEX_NAME
        )
        
        # Запрос пользователя
        user_query = "зрелая нефть с R0 больше 1.0%"
        
        logger.info(f"\nЗапрос пользователя: {user_query}\n")
        
        # Получение топ-10 релевантных документов
        top_k = 10
        df, results = rag.get_relevant_data(
            user_query=user_query,
            top_k=top_k
        )
        
        print(f"Найдено {len(results)} релевантных документов (топ-{top_k}):\n")
        print("="*80)
        
        # Вывод результатов
        for i, result in enumerate(results, 1):
            print(f"\n[{i}] Релевантность: {result.get('_score', 'N/A'):.4f}")
            
            # Текст
            if 'text' in result and result['text']:
                text = result['text']
                preview = text[:150] + "..." if len(text) > 150 else text
                print(f"Текст: {preview}")
            
            # Важные поля
            important_fields = {
                'layer_name': 'Слой',
                'region': 'Регион',
                'depth': 'Глубина',
                'R0': 'R0',
                'Corg': 'Сорг',
                'lon': 'Долгота',
                'lat': 'Широта'
            }
            
            for field, label in important_fields.items():
                if field in result and result[field] is not None:
                    print(f"{label}: {result[field]}")
            
            print("-"*80)
        
        # Альтернативный способ - только список результатов
        print("\n\nАльтернативный способ (простой список):")
        simple_results = rag.get_top_k(user_query, k=5)
        print(f"Получено {len(simple_results)} результатов")
        
    except ConnectionError as e:
        logger.error(f"Ошибка подключения: {e}")
        logger.error("Убедитесь, что OpenSearch запущен и доступен")
    except ValueError as e:
        logger.error(f"Ошибка конфигурации: {e}")
        logger.error("Убедитесь, что индекс существует в OpenSearch")
    except Exception as e:
        logger.error(f"Ошибка: {e}", exc_info=True)


if __name__ == "__main__":
    main()

