"""
Интегрированный модуль для обработки пользовательских запросов:
1. Формализация через LLM
2. Генерация запросов к OpenSearch
3. Выполнение запросов и возврат результатов
"""

import json
import logging
from typing import Dict, Optional, List, Any
from opensearch_test import OpenSearchManager
from query_formalizer import QueryFormalizer, FormalizedQuery

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QueryProcessor:
    """Класс для обработки пользовательских запросов с формализацией и выполнением."""
    
    def __init__(
        self,
        opensearch_manager: OpenSearchManager,
        query_formalizer: Optional[QueryFormalizer] = None
    ):
        """
        Инициализация процессора запросов.
        
        Args:
            opensearch_manager: Экземпляр OpenSearchManager
            query_formalizer: Экземпляр QueryFormalizer (создается автоматически если не указан)
        """
        self.opensearch_manager = opensearch_manager
        self.query_formalizer = query_formalizer or QueryFormalizer()
    
    def process_query(
        self,
        user_query: str,
        index_name: str = "rag_neft",
        use_sql: bool = False
    ) -> Dict[str, Any]:
        """
        Обработка пользовательского запроса: формализация и выполнение.
        
        Args:
            user_query: Запрос пользователя
            index_name: Имя индекса в OpenSearch
            use_sql: Использовать ли SQL вместо Query DSL
            
        Returns:
            Словарь с результатами:
            - formalized_query: формализованный запрос
            - query: сгенерированный запрос (SQL или Query DSL)
            - results: результаты выполнения
            - aggregations: агрегации (если есть)
        """
        logger.info(f"Обработка запроса: {user_query}")
        
        # Шаг 1: Формализация запроса
        formalized = self.query_formalizer.formalize_query(user_query)
        
        if not formalized.attributes and not formalized.location:
            logger.warning("Не удалось извлечь структурированную информацию из запроса")
            return {
                "formalized_query": formalized,
                "query": None,
                "results": [],
                "error": "Не удалось формализовать запрос"
            }
        
        # Шаг 2: Генерация запроса
        if use_sql:
            query = self.query_formalizer.generate_sql_query(formalized, index_name)
            results = self._execute_sql_query(query)
        else:
            query = self.query_formalizer.generate_opensearch_query(formalized)
            results = self._execute_opensearch_query(query, index_name)
        
        # Шаг 3: Обработка результатов
        processed_results = self._process_results(results, formalized)
        
        return {
            "formalized_query": formalized,
            "query": query,
            "results": processed_results.get("hits", []),
            "aggregations": processed_results.get("aggregations", {}),
            "total": processed_results.get("total", 0)
        }
    
    def _execute_opensearch_query(
        self,
        query: Dict[str, Any],
        index_name: str
    ) -> Dict[str, Any]:
        """
        Выполнение OpenSearch Query DSL запроса.
        
        Args:
            query: Query DSL словарь
            index_name: Имя индекса
            
        Returns:
            Результаты поиска
        """
        try:
            response = self.opensearch_manager.client.search(
                index=index_name,
                body=query
            )
            return response
        except Exception as e:
            logger.error(f"Ошибка выполнения OpenSearch запроса: {e}")
            return {"hits": {"hits": []}, "aggregations": {}}
    
    def _execute_sql_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Выполнение SQL запроса через OpenSearch SQL plugin.
        
        Args:
            sql_query: SQL запрос в виде строки
            
        Returns:
            Результаты запроса
        """
        try:
            # OpenSearch SQL API endpoint
            response = self.opensearch_manager.client.transport.perform_request(
                'POST',
                '/_plugins/_sql',
                body={'query': sql_query},
                headers={'Content-Type': 'application/json'}
            )
            return response
        except Exception as e:
            logger.error(f"Ошибка выполнения SQL запроса: {e}")
            return {"hits": {"hits": []}}
    
    def _process_results(
        self,
        results: Dict[str, Any],
        formalized_query: FormalizedQuery
    ) -> Dict[str, Any]:
        """
        Обработка и форматирование результатов запроса.
        
        Args:
            results: Сырые результаты от OpenSearch
            formalized_query: Формализованный запрос
            
        Returns:
            Обработанные результаты
        """
        processed = {
            "hits": [],
            "aggregations": {},
            "total": 0
        }
        
        # Обработка результатов поиска
        if "hits" in results:
            hits = results["hits"].get("hits", [])
            processed["total"] = results["hits"].get("total", {}).get("value", len(hits))
            
            for hit in hits:
                source = hit.get("_source", {})
                processed_hit = {
                    "id": hit.get("_id"),
                    "score": hit.get("_score"),
                    "text": source.get("text", ""),
                }
                
                # Добавляем запрошенные атрибуты
                for attr in formalized_query.attributes:
                    if attr in source:
                        processed_hit[attr] = source[attr]
                
                # Добавляем другие доступные поля
                for field in ["region", "layer_name", "location", "Corg", "R0", "depth"]:
                    if field in source and field not in processed_hit:
                        processed_hit[field] = source[field]
                
                processed["hits"].append(processed_hit)
        
        # Обработка агрегаций
        if "aggregations" in results:
            aggs = results["aggregations"]
            for key, value in aggs.items():
                if isinstance(value, dict):
                    # Извлекаем значение агрегации
                    if "value" in value:
                        processed["aggregations"][key] = value["value"]
                    elif "values" in value:
                        processed["aggregations"][key] = value["values"]
                    else:
                        processed["aggregations"][key] = value
        
        return processed
    
    def format_response(
        self,
        processed_results: Dict[str, Any],
        user_query: str
    ) -> str:
        """
        Форматирование ответа для пользователя в читаемом виде.
        
        Args:
            processed_results: Обработанные результаты
            user_query: Исходный запрос пользователя
            
        Returns:
            Форматированный ответ
        """
        formalized = processed_results.get("formalized_query")
        aggregations = processed_results.get("aggregations", {})
        hits = processed_results.get("results", [])
        total = processed_results.get("total", 0)
        
        response_parts = []
        
        # Заголовок
        response_parts.append(f"Результаты по запросу: \"{user_query}\"")
        response_parts.append("=" * 80)
        
        # Агрегации (если есть)
        if aggregations:
            response_parts.append("\nАгрегированные результаты:")
            for key, value in aggregations.items():
                attr_name = key.split("_")[0]
                action = key.split("_")[1] if "_" in key else ""
                action_name = {
                    "max": "Максимальное",
                    "min": "Минимальное",
                    "avg": "Среднее",
                    "sum": "Сумма",
                    "count": "Количество"
                }.get(action, action)
                
                attr_display = attr_name
                response_parts.append(f"  {action_name} значение {attr_name}: {value}")
        
        # Результаты поиска
        if hits:
            response_parts.append(f"\nНайдено записей: {total}")
            response_parts.append("\nДетальные результаты:")
            
            for i, hit in enumerate(hits[:10], 1):  # Показываем первые 10
                response_parts.append(f"\n{i}. ID: {hit.get('id')}")
                if hit.get('score'):
                    response_parts.append(f"   Релевантность: {hit['score']:.4f}")
                
                # Показываем запрошенные атрибуты
                if formalized and hasattr(formalized, 'attributes'):
                    for attr in formalized.attributes:
                        if attr in hit:
                            response_parts.append(f"   {attr}: {hit[attr]}")
                
                # Показываем текст (первые 200 символов)
                text = hit.get("text", "")
                if text:
                    text_preview = text[:200] + "..." if len(text) > 200 else text
                    response_parts.append(f"   Текст: {text_preview}")
        else:
            response_parts.append("\nРезультаты не найдены.")
        
        return "\n".join(response_parts)


if __name__ == "__main__":
    # Пример использования
    from opensearch_test import OpenSearchManager
    
    # Инициализация OpenSearch
    opensearch_manager = OpenSearchManager(
        host="localhost",
        port=9200,
        use_ssl=True,
        verify_certs=False,
        http_auth=("admin", "Rodion1killer"),
    )
    
    # Проверка подключения
    if not opensearch_manager.check_connection():
        print("Не удалось подключиться к OpenSearch")
        exit(1)
    
    # Создание процессора запросов
    processor = QueryProcessor(opensearch_manager)
    
    # Тестовые запросы
    test_queries = [
        "Найди максимальное значение органического углерода в регионе Каспийского моря",
        "Какая средняя глубина в районе Астрахани?",
        "Покажи все данные по слою эоцен",
    ]
    
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ПРОЦЕССОРА ЗАПРОСОВ")
    print("=" * 80)
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Запрос: {query}")
        print('='*80)
        
        # Обработка запроса
        results = processor.process_query(query, index_name="rag_neft")
        
        # Вывод формализованного запроса
        print("\nФормализованный запрос:")
        print(json.dumps({
            "attributes": results["formalized_query"].attributes,
            "location": results["formalized_query"].location,
            "action": results["formalized_query"].action,
            "filters": results["formalized_query"].filters
        }, ensure_ascii=False, indent=2))
        
        # Вывод сгенерированного запроса
        print("\nСгенерированный запрос:")
        if isinstance(results["query"], dict):
            print(json.dumps(results["query"], ensure_ascii=False, indent=2))
        else:
            print(results["query"])
        
        # Форматированный ответ
        formatted_response = processor.format_response(results, query)
        print("\n" + formatted_response)
