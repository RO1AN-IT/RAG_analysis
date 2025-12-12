# Руководство по работе с OpenSearch

## Обзор

OpenSearch используется в проекте для векторного поиска и RAG (Retrieval Augmented Generation) системы. Этот документ описывает лучшие практики работы с OpenSearch.

## Архитектура

```
Данные (CSV/JSON) 
    ↓
Парсинг и обработка
    ↓
Создание эмбеддингов (Sentence Transformers)
    ↓
Индексация в OpenSearch
    ↓
Семантический поиск
    ↓
RAG с LLM (GPT-4)
```

## Установка и настройка

### 1. Установка OpenSearch

#### Docker (рекомендуется для разработки)
```bash
docker run -d -p 9200:9200 -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=Admin123!" \
  --name opensearch \
  opensearchproject/opensearch:latest
```

#### Локальная установка
```bash
# macOS
brew install opensearch

# Linux
wget https://artifacts.opensearch.org/releases/bundle/opensearch/2.x.x/opensearch-2.x.x-linux-x64.tar.gz
tar -xzf opensearch-2.x.x-linux-x64.tar.gz
cd opensearch-2.x.x
./bin/opensearch
```

### 2. Установка Python зависимостей

```bash
pip install opensearch-py sentence-transformers langchain langchain-openai langchain-community
```

### 3. Настройка через .env файл (рекомендуется)

Файл `.env` уже создан в корне проекта. Отредактируйте его своими данными:

```bash
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=true  # Включить HTTPS
OPENSEARCH_VERIFY_CERTS=true  # Проверять SSL сертификаты
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your_password
OPENAI_API_KEY=your_openai_api_key_here
```

**Для HTTPS подключения:**
- Установите `OPENSEARCH_USE_SSL=true`
- Порт обычно 443 (стандартный HTTPS) или 9200 (если OpenSearch настроен на HTTPS)
- `OPENSEARCH_VERIFY_CERTS=true` для проверки сертификатов (рекомендуется)
- `OPENSEARCH_VERIFY_CERTS=false` только для самоподписанных сертификатов в разработке

**Важно:** Файл `.env` добавлен в `.gitignore` и не будет попадать в git репозиторий.

## Использование

### Базовое использование

#### HTTP подключение
```python
from opensearch_manager import OpenSearchManager
import pandas as pd

# Инициализация для HTTP
manager = OpenSearchManager(
    host="localhost",
    port=9200,
    use_ssl=False,
    embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
```

#### HTTPS подключение (рекомендуется)
```python
from opensearch_manager import OpenSearchManager
import pandas as pd

# Инициализация для HTTPS
manager = OpenSearchManager(
    host="localhost",
    port=9200,  # Или 443 для стандартного HTTPS
    use_ssl=True,  # Включить HTTPS
    verify_certs=True,  # Проверять сертификаты
    http_auth=("admin", "password"),  # Если требуется аутентификация
    embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# Проверка подключения
if not manager.check_connection():
    print("Ошибка подключения")
    exit(1)

# Создание индекса
manager.create_index("caspian_data")

# Загрузка данных
df = pd.read_csv("data.csv")

# Индексация
manager.index_dataframe(df, "caspian_data", batch_size=100)

# Поиск
results = manager.search("месторождения нефти", "caspian_data", top_k=5)
for result in results:
    print(f"Score: {result['score']}")
    print(f"Text: {result['text']}")
```

### Использование RAG системы

#### HTTP подключение
```python
from rag_opensearch_integration import CaspianRAGSystem

# Инициализация для HTTP
rag = CaspianRAGSystem(
    opensearch_host="localhost",
    opensearch_port=9200,
    opensearch_use_ssl=False,
    index_name="caspian_data"
)
```

#### HTTPS подключение (рекомендуется)
```python
from rag_opensearch_integration import CaspianRAGSystem

# Инициализация для HTTPS
rag = CaspianRAGSystem(
    opensearch_host="localhost",
    opensearch_port=9200,  # Или 443 для стандартного HTTPS
    opensearch_use_ssl=True,  # Включить HTTPS
    opensearch_verify_certs=True,  # Проверять сертификаты
    opensearch_auth=("admin", "password"),  # Если требуется аутентификация
    index_name="caspian_data"
)

# Индексация данных
df = pd.read_csv("data.csv")
rag.index_data(df)

# Задать вопрос
result = rag.answer_question("Какие месторождения нефти есть в регионе?")
print(result['answer'])
print(f"Источники: {len(result['sources'])}")
```

## Лучшие практики

### 1. Выбор модели эмбеддингов

**Для русского языка:**
- `paraphrase-multilingual-MiniLM-L12-v2` - быстрая, хорошее качество
- `paraphrase-multilingual-mpnet-base-v2` - лучшее качество, медленнее
- `intfloat/multilingual-e5-base` - отличное качество для многоязычных данных

**Рекомендация для проекта:**
```python
embedding_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### 2. Настройка индекса

**Для небольших данных (< 1M документов):**
```python
settings = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index": {
        "knn": True,
        "knn.algo_param.ef_search": 100
    }
}
```

**Для больших данных (> 1M документов):**
```python
settings = {
    "number_of_shards": 3,
    "number_of_replicas": 1,
    "index": {
        "knn": True,
        "knn.algo_param.ef_search": 200
    }
}
```

### 3. Батчинг при индексации

```python
# Оптимальный размер батча зависит от размера документов
# Для текстовых данных: 50-200
# Для больших документов: 10-50

manager.index_dataframe(
    df,
    index_name,
    batch_size=100  # Оптимально для большинства случаев
)
```

### 4. Оптимизация поиска

```python
# Для точного поиска
results = manager.search(
    query,
    index_name,
    top_k=10,  # Больше результатов = больше контекста для LLM
    filter_dict={"layer": "Месторождения"}  # Фильтрация по слою
)

# Для быстрого поиска
results = manager.search(
    query,
    index_name,
    top_k=5  # Меньше результатов = быстрее
)
```

### 5. Обработка ошибок

```python
try:
    results = manager.search(query, index_name)
except Exception as e:
    logger.error(f"Ошибка поиска: {e}")
    # Fallback на обычный текстовый поиск
    results = []
```

## Производительность

### Оптимизация индексации

1. **Используйте батчинг**: Всегда используйте `batch_size` > 1
2. **Параллельная обработка**: Для больших данных используйте multiprocessing
3. **Кэширование эмбеддингов**: Кэшируйте эмбеддинги для повторяющихся текстов

```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def get_cached_embedding(text):
    return manager.embedding_model.encode(text)
```

### Оптимизация поиска

1. **Используйте фильтры**: Фильтрация уменьшает пространство поиска
2. **Настройте ef_search**: Больше ef_search = точнее, но медленнее
3. **Кэшируйте частые запросы**: Используйте Redis для кэширования

## Мониторинг

### Проверка здоровья кластера

```python
health = manager.client.cluster.health()
print(f"Status: {health['status']}")
print(f"Nodes: {health['number_of_nodes']}")
```

### Статистика индекса

```python
stats = manager.get_index_stats("caspian_data")
print(f"Документов: {stats['doc_count']}")
print(f"Размер: {stats['size'] / 1024 / 1024:.2f} MB")
```

### Мониторинг производительности

```python
# Время индексации
import time
start = time.time()
manager.index_dataframe(df, index_name)
print(f"Время индексации: {time.time() - start:.2f} сек")

# Время поиска
start = time.time()
results = manager.search(query, index_name)
print(f"Время поиска: {time.time() - start:.3f} сек")
```

## Безопасность

### 1. Аутентификация

```python
manager = OpenSearchManager(
    host="localhost",
    port=9200,
    http_auth=("admin", "secure_password")
)
```

### 2. SSL/TLS

```python
manager = OpenSearchManager(
    host="opensearch.example.com",
    port=443,
    use_ssl=True,
    verify_certs=True
)
```

### 3. Ограничение доступа

- Используйте роли и пользователей в OpenSearch
- Ограничьте доступ к индексам по IP
- Используйте VPN для доступа к продакшн кластеру

## Troubleshooting

### Проблема: Медленная индексация

**Решение:**
- Увеличьте `batch_size`
- Уменьшите размерность эмбеддингов
- Используйте более быструю модель

### Проблема: Низкое качество поиска

**Решение:**
- Попробуйте другую модель эмбеддингов
- Увеличьте `top_k` для большего контекста
- Улучшите создание текста из данных (`create_text_from_row`)

### Проблема: Ошибки памяти

**Решение:**
- Уменьшите `batch_size`
- Уменьшите `number_of_shards`
- Используйте потоковую обработку

### Проблема: Несоответствие размерности векторов

**Решение:**
- Убедитесь, что размерность в `create_index` совпадает с моделью
- Пересоздайте индекс с правильной размерностью

## Примеры использования

### Пример 1: Полный пайплайн

```python
from opensearch_manager import OpenSearchManager
from json_to_csv_improved import json_to_csv
import pandas as pd

# 1. Конвертация JSON в CSV
df = json_to_csv("parsed_project.json", "data.csv")

# 2. Инициализация OpenSearch
manager = OpenSearchManager(host="localhost", port=9200)

# 3. Создание индекса
manager.create_index("caspian_data")

# 4. Индексация данных
manager.index_dataframe(df, "caspian_data", batch_size=100)

# 5. Поиск
results = manager.search("месторождения", "caspian_data", top_k=10)
```

### Пример 2: RAG с фильтрацией

```python
from rag_opensearch_integration import CaspianRAGSystem

rag = CaspianRAGSystem(index_name="caspian_data")

# Поиск с фильтром по слою
result = rag.answer_question(
    "Какие месторождения есть?",
    filters={"layer": "Месторождения"},
    top_k=5
)
```

### Пример 3: Массовая индексация

```python
import pandas as pd
from opensearch_manager import OpenSearchManager

manager = OpenSearchManager()

# Чтение больших файлов по частям
chunk_size = 10000
for chunk in pd.read_csv("large_data.csv", chunksize=chunk_size):
    manager.index_dataframe(chunk, "caspian_data", batch_size=100)
```

## Дополнительные ресурсы

- [OpenSearch Documentation](https://opensearch.org/docs/)
- [LangChain OpenSearch Integration](https://python.langchain.com/docs/integrations/vectorstores/opensearch)
- [Sentence Transformers Models](https://www.sbert.net/docs/pretrained_models.html)

## Рекомендации для проекта

1. **Для разработки**: Используйте Docker контейнер OpenSearch
2. **Для продакшна**: Настройте кластер с репликацией
3. **Модель эмбеддингов**: `paraphrase-multilingual-MiniLM-L12-v2` - хороший баланс скорости и качества
4. **Размер батча**: 100 документов оптимально для большинства случаев
5. **Мониторинг**: Регулярно проверяйте статистику индексов

