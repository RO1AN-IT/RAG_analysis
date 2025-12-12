"""
Модуль для формализации пользовательских запросов и генерации SQL/Query DSL запросов к OpenSearch.

Функциональность:
- Формализация запросов через LLM (GigaChat)
- Извлечение ключевых признаков, места и действия
- Генерация запросов к OpenSearch
"""

import json
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
from gigachat import GigaChat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GigaChat credentials
GIGACHAT_CREDENTIALS = "MDE5YjA0YmYtMDNlMy03ZmVjLTgyN2EtNDI5OGFhYmM4YzlhOjVjMGJhYWRmLTQ4ZjktNGNkNC1iNjBkLTRhODVjYTY5Y2RmNQ=="

# Доступные признаки в БД
AVAILABLE_ATTRIBUTES = {
    "Corg": "Органический углерод",
    "R0": "Степень зрелости органического вещества",
    "depth": "Глубина",
    "region": "Регион",
    "layer_name": "Название слоя",
    "location": "Географическое местоположение"
}

# Доступные действия/флаги
AVAILABLE_ACTIONS = {
    "max": "максимальное значение",
    "min": "минимальное значение",
    "avg": "среднее значение",
    "sum": "сумма",
    "count": "количество",
    "list": "список всех значений"
}


@dataclass
class FormalizedQuery:
    """Структурированное представление формализованного запроса."""
    attributes: List[str]  # Список признаков для запроса
    location: Optional[str] = None  # Место/регион для фильтрации
    action: Optional[str] = None  # Действие (max, min, avg, etc.)
    filters: Dict[str, Any] = None  # Дополнительные фильтры
    raw_query: str = ""  # Исходный запрос пользователя
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}


class QueryFormalizer:
    """Класс для формализации пользовательских запросов через LLM."""
    
    def __init__(self, credentials: str = GIGACHAT_CREDENTIALS):
        """
        Инициализация формализатора запросов.
        
        Args:
            credentials: Credentials для GigaChat
        """
        self.credentials = credentials
        self._giga = None
    
    def _get_llm(self) -> GigaChat:
        """Получение экземпляра GigaChat."""
        if self._giga is None:
            self._giga = GigaChat(
                credentials=self.credentials,
                verify_ssl_certs=False
            )
        return self._giga
    
    def _create_formalization_prompt(self, user_query: str) -> str:
        """
        Создание жесткого промпта для формализации запроса.
        
        Args:
            user_query: Запрос пользователя
            
        Returns:
            Промпт для LLM
        """
        available_attrs = "\n".join([f"- {k}: {v}" for k, v in AVAILABLE_ATTRIBUTES.items()])
        available_actions = "\n".join([f"- {k}: {v}" for k, v in AVAILABLE_ACTIONS.items()])
        
        prompt = f"""Ты - эксперт по анализу геологических данных Каспийского моря. 
Твоя задача - формализовать запрос пользователя и извлечь структурированную информацию.

Доступные признаки в базе данных:
{available_attrs}

Доступные действия/флаги:
{available_actions}

Запрос пользователя: "{user_query}"

Проанализируй запрос и верни ТОЛЬКО валидный JSON в следующем формате:
{{
    "attributes": ["список", "признаков", "для", "запроса"],
    "location": "название региона или места (если указано, иначе null)",
    "action": "одно из действий: max, min, avg, sum, count, list (если указано, иначе null)",
    "filters": {{"дополнительные": "фильтры в формате ключ-значение"}}
}}

Правила:
1. В attributes укажи ТОЛЬКО те признаки, которые упоминаются в запросе или логически необходимы
2. Если пользователь спрашивает про конкретное место/регион, укажи его в location
3. Если пользователь просит найти максимум/минимум/среднее, укажи соответствующее действие
4. Если действие не указано явно, но логически требуется (например, "найти наибольшее"), определи его
5. Если запрос неясен или некорректен, верни пустые списки и null значения
6. Используй ТОЛЬКО доступные признаки и действия из списков выше

Верни ТОЛЬКО JSON, без дополнительного текста."""
        
        return prompt
    
    def formalize_query(self, user_query: str) -> FormalizedQuery:
        """
        Формализация пользовательского запроса через LLM.
        
        Args:
            user_query: Запрос пользователя
            
        Returns:
            FormalizedQuery объект со структурированными данными
        """
        logger.info(f"Формализация запроса: {user_query}")
        
        prompt = self._create_formalization_prompt(user_query)
        
        try:
            with self._get_llm() as giga:
                response = giga.chat(prompt)
                response_text = response.choices[0].message.content.strip()
                
                # Извлечение JSON из ответа (может быть обернут в markdown код)
                if "```json" in response_text:
                    response_text = response_text.split("```json")[1].split("```")[0].strip()
                elif "```" in response_text:
                    response_text = response_text.split("```")[1].split("```")[0].strip()
                
                # Парсинг JSON
                try:
                    parsed = json.loads(response_text)
                except json.JSONDecodeError:
                    # Попытка найти JSON в тексте
                    import re
                    json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                    if json_match:
                        parsed = json.loads(json_match.group())
                    else:
                        logger.error(f"Не удалось распарсить JSON из ответа: {response_text}")
                        return FormalizedQuery(
                            attributes=[],
                            raw_query=user_query
                        )
                
                # Валидация и создание объекта
                attributes = parsed.get("attributes", [])
                if not isinstance(attributes, list):
                    attributes = []
                
                # Фильтрация только доступных признаков
                attributes = [attr for attr in attributes if attr in AVAILABLE_ATTRIBUTES]
                
                formalized = FormalizedQuery(
                    attributes=attributes,
                    location=parsed.get("location"),
                    action=parsed.get("action"),
                    filters=parsed.get("filters", {}),
                    raw_query=user_query
                )
                
                # Валидация действия
                if formalized.action and formalized.action not in AVAILABLE_ACTIONS:
                    logger.warning(f"Неизвестное действие: {formalized.action}, устанавливаю null")
                    formalized.action = None
                
                logger.info(f"Формализованный запрос: {asdict(formalized)}")
                return formalized
                
        except Exception as e:
            logger.error(f"Ошибка при формализации запроса: {e}")
            return FormalizedQuery(
                attributes=[],
                raw_query=user_query
            )
    
    def generate_opensearch_query(self, formalized_query: FormalizedQuery) -> Dict[str, Any]:
        """
        Генерация OpenSearch Query DSL на основе формализованного запроса.
        
        Args:
            formalized_query: FormalizedQuery объект
            
        Returns:
            OpenSearch Query DSL словарь
        """
        query_parts = []
        
        # Фильтр по региону/месту
        if formalized_query.location:
            query_parts.append({
                "match": {
                    "region": {
                        "query": formalized_query.location,
                        "fuzziness": "AUTO"
                    }
                }
            })
        
        # Дополнительные фильтры
        for key, value in formalized_query.filters.items():
            if key in AVAILABLE_ATTRIBUTES:
                if isinstance(value, (int, float)):
                    query_parts.append({
                        "range": {
                            key: {"gte": value}
                        }
                    })
                else:
                    query_parts.append({
                        "match": {
                            key: {
                                "query": str(value),
                                "fuzziness": "AUTO"
                            }
                        }
                    })
        
        # Базовая структура запроса
        if query_parts:
            query = {
                "bool": {
                    "must": query_parts
                }
            }
        else:
            query = {"match_all": {}}
        
        # Агрегации для действий
        aggs = {}
        if formalized_query.action and formalized_query.attributes:
            for attr in formalized_query.attributes:
                if attr in ['Corg', 'R0', 'depth']:  # Числовые поля
                    if formalized_query.action == "max":
                        aggs[f"{attr}_max"] = {"max": {"field": attr}}
                    elif formalized_query.action == "min":
                        aggs[f"{attr}_min"] = {"min": {"field": attr}}
                    elif formalized_query.action == "avg":
                        aggs[f"{attr}_avg"] = {"avg": {"field": attr}}
                    elif formalized_query.action == "sum":
                        aggs[f"{attr}_sum"] = {"sum": {"field": attr}}
                    elif formalized_query.action == "count":
                        aggs[f"{attr}_count"] = {"value_count": {"field": attr}}
        
        opensearch_query = {
            "query": query,
            "size": 100  # Количество результатов
        }
        
        if aggs:
            opensearch_query["aggs"] = aggs
        
        return opensearch_query
    
    def generate_sql_query(self, formalized_query: FormalizedQuery, index_name: str = "rag_neft") -> str:
        """
        Генерация SQL запроса для OpenSearch SQL plugin.
        
        Args:
            formalized_query: FormalizedQuery объект
            index_name: Имя индекса в OpenSearch
            
        Returns:
            SQL запрос в виде строки
        """
        if not formalized_query.attributes:
            return f"SELECT * FROM {index_name} LIMIT 100"
        
        # Выбор полей
        select_fields = ["text"]
        for attr in formalized_query.attributes:
            if attr in AVAILABLE_ATTRIBUTES:
                select_fields.append(attr)
        
        select_clause = ", ".join(select_fields)
        
        # WHERE условия
        where_clauses = []
        if formalized_query.location:
            where_clauses.append(f"region LIKE '%{formalized_query.location}%'")
        
        for key, value in formalized_query.filters.items():
            if key in AVAILABLE_ATTRIBUTES:
                if isinstance(value, (int, float)):
                    where_clauses.append(f"{key} >= {value}")
                else:
                    where_clauses.append(f"{key} = '{value}'")
        
        where_clause = " AND ".join(where_clauses) if where_clauses else ""
        
        # GROUP BY и агрегации для действий
        group_by = ""
        having = ""
        if formalized_query.action and formalized_query.attributes:
            numeric_attrs = [attr for attr in formalized_query.attributes if attr in ['Corg', 'R0', 'depth']]
            if numeric_attrs:
                action_map = {
                    "max": "MAX",
                    "min": "MIN",
                    "avg": "AVG",
                    "sum": "SUM",
                    "count": "COUNT"
                }
                action_sql = action_map.get(formalized_query.action, "")
                if action_sql:
                    # Заменяем поля в SELECT на агрегации
                    select_fields = []
                    for attr in numeric_attrs:
                        select_fields.append(f"{action_sql}({attr}) as {attr}_{formalized_query.action}")
                    select_clause = ", ".join(select_fields)
        
        # Формирование SQL
        sql = f"SELECT {select_clause} FROM {index_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if group_by:
            sql += f" GROUP BY {group_by}"
        if having:
            sql += f" HAVING {having}"
        sql += " LIMIT 100"
        
        return sql


if __name__ == "__main__":
    # Пример использования
    formalizer = QueryFormalizer()
    
    # Тестовые запросы
    test_queries = [
        "Найди максимальное значение органического углерода в регионе Каспийского моря"
    ]
    
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ ФОРМАЛИЗАТОРА ЗАПРОСОВ")
    print("=" * 80)
    
    for query in test_queries:
        print(f"\nЗапрос: {query}")
        print("-" * 80)
        
        # Формализация
        formalized = formalizer.formalize_query(query)
        print(f"Формализованный запрос:")
        print(json.dumps(asdict(formalized), ensure_ascii=False, indent=2))
        
        # Генерация OpenSearch Query DSL
        opensearch_query = formalizer.generate_opensearch_query(formalized)
        print(f"\nOpenSearch Query DSL:")
        print(json.dumps(opensearch_query, ensure_ascii=False, indent=2))
        
        # Генерация SQL запроса
        sql_query = formalizer.generate_sql_query(formalized)
        print(f"\nSQL запрос:")
        print(sql_query)
        
        print("\n" + "=" * 80)
