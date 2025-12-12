# Система формализации и обработки запросов

## Описание

Реализация варианта 2 из файла `idea`: система формализует пользовательские запросы через LLM (GigaChat), извлекает ключевые признаки, место и действие, затем генерирует SQL/Query DSL запросы к OpenSearch.

## Архитектура

```
Пользовательский запрос
    ↓
QueryFormalizer (формализация через LLM)
    ↓
Извлечение: признаки, место, действие
    ↓
Генерация запроса (SQL или Query DSL)
    ↓
QueryProcessor (выполнение в OpenSearch)
    ↓
Обработка и форматирование результатов
    ↓
Ответ пользователю
```

## Компоненты

### 1. `query_formalizer.py`
- **QueryFormalizer**: Класс для формализации запросов через GigaChat
- **FormalizedQuery**: Структурированное представление запроса
- Извлекает:
  - `attributes`: список признаков (Corg, R0, depth, region, layer_name, location)
  - `location`: место/регион для фильтрации
  - `action`: действие (max, min, avg, sum, count, list)
  - `filters`: дополнительные фильтры

### 2. `query_processor.py`
- **QueryProcessor**: Интегрированный процессор запросов
- Объединяет формализацию и выполнение
- Обрабатывает результаты и форматирует ответы

## Использование

### Базовый пример

```python
from opensearch_test import OpenSearchManager
from query_processor import QueryProcessor

# Инициализация OpenSearch
opensearch_manager = OpenSearchManager(
    host="localhost",
    port=9200,
    use_ssl=True,
    verify_certs=False,
    http_auth=("admin", "password"),
)

# Создание процессора
processor = QueryProcessor(opensearch_manager)

# Обработка запроса
results = processor.process_query(
    "Найди максимальное значение органического углерода в регионе Каспийского моря",
    index_name="rag_neft"
)

# Форматированный ответ
formatted = processor.format_response(results, user_query)
print(formatted)
```

### Только формализация

```python
from query_formalizer import QueryFormalizer

formalizer = QueryFormalizer()

# Формализация запроса
formalized = formalizer.formalize_query(
    "Какая средняя глубина в районе Астрахани?"
)

print(f"Признаки: {formalized.attributes}")
print(f"Место: {formalized.location}")
print(f"Действие: {formalized.action}")

# Генерация SQL запроса
sql = formalizer.generate_sql_query(formalized, "rag_neft")
print(f"SQL: {sql}")

# Генерация OpenSearch Query DSL
query_dsl = formalizer.generate_opensearch_query(formalized)
print(f"Query DSL: {query_dsl}")
```

## Доступные признаки

- **Corg**: Органический углерод (float)
- **R0**: Степень зрелости органического вещества (float)
- **depth**: Глубина (float)
- **region**: Регион (keyword)
- **layer_name**: Название слоя (keyword)
- **location**: Географическое местоположение (geo_point)

## Доступные действия

- **max**: Максимальное значение
- **min**: Минимальное значение
- **avg**: Среднее значение
- **sum**: Сумма
- **count**: Количество
- **list**: Список всех значений

## Примеры запросов

1. **"Найди максимальное значение органического углерода в регионе Каспийского моря"**
   - Признаки: `["Corg"]`
   - Место: `"Каспийского моря"`
   - Действие: `"max"`

2. **"Какая средняя глубина в районе Астрахани?"**
   - Признаки: `["depth"]`
   - Место: `"Астрахани"`
   - Действие: `"avg"`

3. **"Покажи все данные по слою эоцен"**
   - Признаки: `[]`
   - Место: `null`
   - Действие: `null`
   - Фильтры: `{"layer_name": "эоцен"}`

## Структура ответа

```python
{
    "formalized_query": FormalizedQuery(...),
    "query": {...},  # SQL или Query DSL
    "results": [...],  # Список найденных документов
    "aggregations": {...},  # Агрегированные значения
    "total": 100  # Общее количество результатов
}
```

## Запуск тестов

```bash
# Тест формализатора
python query_formalizer.py

# Тест процессора (требует подключения к OpenSearch)
python query_processor.py
```

## Зависимости

- `gigachat`: для работы с GigaChat LLM
- `opensearch-py`: для работы с OpenSearch
- `sentence-transformers`: для эмбеддингов (используется в opensearch_test.py)

## Примечания

1. **Жесткий промпт**: Промпт для формализации жестко задан и оптимизирован для извлечения структурированной информации
2. **Валидация**: Система валидирует извлеченные признаки и действия против доступных списков
3. **Обработка ошибок**: При ошибках формализации возвращается пустой FormalizedQuery
4. **SQL vs Query DSL**: Можно использовать как SQL (через OpenSearch SQL plugin), так и Query DSL
