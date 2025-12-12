# Настройка HTTPS для OpenSearch

## Быстрая настройка

### Вариант 1: Через .env файл (рекомендуется)

Создайте файл `.env` в корне проекта (уже создан):

```bash
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=true
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=your_password
```

Теперь можно использовать без указания параметров - они загрузятся автоматически:

```python
from opensearch_manager import OpenSearchManager

# Параметры загрузятся из .env автоматически
manager = OpenSearchManager()
```

### Вариант 2: Через параметры при инициализации

```python
from opensearch_manager import OpenSearchManager

manager = OpenSearchManager(
    host="your-opensearch-host.com",
    port=9200,  # Или 443
    use_ssl=True,  # Включить HTTPS
    verify_certs=True,  # Проверять сертификаты
    http_auth=("username", "password")  # Если требуется
)
```

### Вариант 3: Через переменные окружения (вручную)

Установите переменные окружения:

```bash
export OPENSEARCH_HOST=your-opensearch-host.com
export OPENSEARCH_PORT=9200
export OPENSEARCH_USE_SSL=true
export OPENSEARCH_VERIFY_CERTS=true
export OPENSEARCH_USERNAME=admin
export OPENSEARCH_PASSWORD=your_password
```

Затем используйте без указания параметров:

```python
from opensearch_manager import OpenSearchManager

# Параметры будут взяты из переменных окружения
manager = OpenSearchManager()
```

### Вариант 4: Для RAG системы

```python
from rag_opensearch_integration import CaspianRAGSystem

rag = CaspianRAGSystem(
    opensearch_host="your-opensearch-host.com",
    opensearch_port=9200,
    opensearch_use_ssl=True,
    opensearch_verify_certs=True,
    opensearch_auth=("username", "password")
)
```

## Настройки SSL

### `verify_certs=True` (рекомендуется для продакшена)
- Проверяет SSL сертификаты
- Используется в продакшене с валидными сертификатами
- Безопасно

### `verify_certs=False` (для локальной разработки)
- Не проверяет SSL сертификаты
- **Используйте для самоподписанных сертификатов** (как в вашем случае)
- Небезопасно для продакшена
- **Важно:** Если получаете ошибку `CERTIFICATE_VERIFY_FAILED`, установите `OPENSEARCH_VERIFY_CERTS=false` в `.env`

## Автоопределение HTTPS

Система автоматически определяет использование HTTPS если:
- Порт = 443 (стандартный HTTPS порт)
- Установлена переменная окружения `OPENSEARCH_USE_SSL=true`

## Проверка подключения

```python
manager = OpenSearchManager(
    host="your-host.com",
    port=9200,
    use_ssl=True,
    verify_certs=True
)

if manager.check_connection():
    print("✓ Подключение успешно!")
else:
    print("✗ Ошибка подключения")
```

## Troubleshooting

### Ошибка: SSL certificate verification failed

**Решение:** Если используете самоподписанный сертификат в разработке:
```python
manager = OpenSearchManager(
    use_ssl=True,
    verify_certs=False  # Только для разработки!
)
```

### Ошибка: Connection refused

**Решение:** Проверьте:
- Правильность хоста и порта
- Доступность OpenSearch сервера
- Настройки firewall

### Ошибка: Authentication failed

**Решение:** Проверьте учетные данные:
```python
manager = OpenSearchManager(
    http_auth=("correct_username", "correct_password")
)
```

