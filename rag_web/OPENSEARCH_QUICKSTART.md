# OpenSearch - Быстрый старт

Краткая шпаргалка для развертывания и управления OpenSearch.

## 🚀 Быстрое развертывание

```bash
# 1. Перейти в директорию проекта
cd ~/projects/RAG_analysis/rag_web

# 2. Запустить OpenSearch
docker compose -f docker-compose.opensearch.yml up -d

# 3. Проверить статус
docker compose -f docker-compose.opensearch.yml ps

# 4. Проверить доступность
curl http://localhost:9200
```

## 📋 Основные команды

### Управление контейнером

```bash
# Запустить
docker compose -f docker-compose.opensearch.yml up -d

# Остановить
docker compose -f docker-compose.opensearch.yml stop

# Перезапустить
docker compose -f docker-compose.opensearch.yml restart

# Остановить и удалить
docker compose -f docker-compose.opensearch.yml down

# Остановить и удалить + данные (ОСТОРОЖНО!)
docker compose -f docker-compose.opensearch.yml down -v

# Логи
docker compose -f docker-compose.opensearch.yml logs -f

# Статус
docker compose -f docker-compose.opensearch.yml ps
```

### Проверка работоспособности

```bash
# Проверить API
curl http://localhost:9200

# Список индексов
curl http://localhost:9200/_cat/indices?v

# Здоровье кластера
curl http://localhost:9200/_cluster/health?pretty

# Количество документов
curl http://localhost:9200/rag_descriptions/_count
curl http://localhost:9200/rag_layers/_count
```

### Работа с данными

```bash
# Экспорт данных
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
python export_opensearch.py

# Импорт данных
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
export OPENSEARCH_USE_SSL=False
python import_opensearch.py
```

## ⚙️ Настройка backend

В файле `backend/.env`:

```env
OPENSEARCH_HOST=localhost
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=False
OPENSEARCH_VERIFY_CERTS=False
OPENSEARCH_AUTH_USERNAME=
OPENSEARCH_AUTH_PASSWORD=
```

После изменения `.env` перезапустите backend:
```bash
sudo systemctl restart rag_web
# или
docker compose restart backend
```

## 🔧 Настройка памяти

В `docker-compose.opensearch.yml` измените строку 16:

```yaml
- OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m  # Минимум (512MB)
- OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g      # Рекомендуется (1GB)
- OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g      # Для больших индексов (2GB)
```

После изменения перезапустите:
```bash
docker compose -f docker-compose.opensearch.yml restart
```

## 🔒 Безопасность

### Ограничить доступ только для localhost

В `docker-compose.opensearch.yml` измените строку 28:

```yaml
ports:
  - "127.0.0.1:9200:9200"  # Только localhost
```

### Включить аутентификацию

1. В `docker-compose.opensearch.yml`:
```yaml
- plugins.security.disabled=false
- OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-strong-password
```

2. В `backend/.env`:
```env
OPENSEARCH_AUTH_USERNAME=admin
OPENSEARCH_AUTH_PASSWORD=your-strong-password
```

3. Перезапустить:
```bash
docker compose -f docker-compose.opensearch.yml down
docker compose -f docker-compose.opensearch.yml up -d
```

## 📊 Мониторинг

```bash
# Использование ресурсов
docker stats opensearch

# Логи в реальном времени
docker compose -f docker-compose.opensearch.yml logs -f

# Здоровье кластера
curl http://localhost:9200/_cluster/health?pretty
```

## 🐛 Устранение проблем

### Конфликт имени контейнера

**Ошибка:** `Conflict. The container name "/opensearch" is already in use`

```bash
# Решение: удалить старый контейнер
docker compose -f docker-compose.opensearch.yml down
docker compose -f docker-compose.opensearch.yml up -d

# Или вручную:
docker stop opensearch opensearch-dashboards
docker rm opensearch opensearch-dashboards
docker compose -f docker-compose.opensearch.yml up -d
```

### OpenSearch не запускается

```bash
# Проверить логи
docker compose -f docker-compose.opensearch.yml logs

# Проверить память
free -h

# Проверить порт
sudo netstat -tlnp | grep 9200
```

### Backend не подключается

```bash
# Проверить, что OpenSearch запущен
docker ps | grep opensearch

# Проверить доступность
curl http://localhost:9200

# Проверить переменные окружения
cd backend && cat .env | grep OPENSEARCH
```

## 📚 Дополнительная информация

Полная документация: `OPENSEARCH_DEPLOYMENT.md`

