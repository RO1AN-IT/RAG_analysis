# Устранение неполадок Docker Compose

## Проблема: Файлы test_final_v2.py и prompts.py не найдены

Если файлы лежат на директорию выше (в корне проекта):

### Вариант 1: Использовать volumes (рекомендуется)

В `docker-compose.yml` уже настроено монтирование файлов:

```yaml
volumes:
  - ../test_final_v2.py:/app/test_final_v2.py:ro
  - ../prompts.py:/app/prompts.py:ro
```

Проверить, что файлы монтируются:
```bash
docker compose exec backend ls -la /app/test_final_v2.py /app/prompts.py
```

### Вариант 2: Изменить context в docker-compose.yml

Если файлы лежат еще выше, измените context:

```yaml
backend:
  build:
    context: ../..  # две директории вверх
    dockerfile: rag_web/Dockerfile.backend
```

### Вариант 3: Скопировать файлы в правильное место

```bash
# На сервере скопировать файлы в нужную директорию
cp ~/test_final_v2.py ~/RAG_analysis/
cp ~/prompts.py ~/RAG_analysis/
```

## Проблема: 404 Not Found для /api/

Если backend возвращает 404 для `/api/`, проверьте:

### 1. Проверить конкретные endpoints

```bash
# /api/ не существует, проверьте конкретные endpoints:
curl http://localhost:8000/api/query/
curl http://localhost:8000/api/heygen/generate/
```

### 2. Проверить, что файлы test_final_v2.py и prompts.py скопированы

```bash
# Зайти в контейнер
docker compose exec backend bash

# Проверить наличие файлов
ls -la /app/test_final_v2.py /app/prompts.py

# Если файлов нет - пересобрать контейнер
exit
docker compose down
docker compose build --no-cache backend
docker compose up -d
```

### 3. Проверить логи на ошибки импорта

```bash
# Посмотреть логи backend
docker compose logs backend | grep -i error

# Если есть ошибки импорта - файлы не скопированы или пути неправильные
```

### 4. Проверить структуру проекта

Убедитесь, что структура проекта правильная:

```
RAG_analysis/              <- корень проекта
├── test_final_v2.py       <- должен быть здесь
├── prompts.py             <- должен быть здесь
└── rag_web/
    ├── docker-compose.yml
    ├── Dockerfile.backend
    └── backend/
```

В `docker-compose.yml` context указан как `..` (родительская директория), поэтому Dockerfile должен правильно копировать файлы из корня.

## Проблема: Ошибки импорта test_final_v2

Если появляются ошибки импорта:

```bash
# 1. Проверить, что файлы есть в контейнере
docker compose exec backend ls -la /app/ | grep -E "test_final_v2|prompts"

# 2. Проверить импорт
docker compose exec backend python -c "import sys; sys.path.insert(0, '/app'); import test_final_v2; print('OK')"

# 3. Если не работает - пересобрать контейнер
docker compose down
docker compose build --no-cache backend
docker compose up -d
```

## Проблема: Порт уже занят

```bash
# Остановить процессы, использующие порты
sudo systemctl stop nginx rag_web
sudo systemctl disable nginx rag_web

# Или убить процессы напрямую
sudo lsof -i :80 -t | xargs sudo kill -9
sudo lsof -i :8000 -t | xargs sudo kill -9

# Проверить, что порты свободны
sudo lsof -i :80
sudo lsof -i :8000
```

## Проблема: Worker убивается из-за нехватки памяти (SIGKILL! Perhaps out of memory?)

Это означает, что процесс Gunicorn worker превысил доступный лимит RAM.

### 1. Проверить использование памяти контейнера

```bash
# Посмотреть статистику использования памяти
docker stats rag_web_backend

# Или для всех контейнеров
docker stats

# Проверить, сколько памяти доступно на сервере
free -h
```

### 2. Увеличить лимит памяти в docker-compose.yml

**Вариант А: Для Docker Compose версии 3.x+ (рекомендуется)**

В `docker-compose.yml` добавьте:

```yaml
backend:
  deploy:
    resources:
      limits:
        memory: 4G  # Для 1 ядра и 8GB RAM - 4GB для backend
      reservations:
        memory: 1G
```

**Вариант Б: Для старых версий Docker Compose (если deploy не работает)**

```yaml
backend:
  mem_limit: 2g  # Лимит памяти в байтах (2GB)
  mem_reservation: 512m  # Минимальная гарантированная память
```

После изменения:
```bash
docker compose down
docker compose up -d
```

**Проверить версию Docker Compose:**
```bash
docker compose version || docker-compose --version
```

### 3. Уменьшить количество workers

Если память ограничена, уменьшите количество workers в команде Gunicorn:

```yaml
command: >
  sh -c "
    python manage.py migrate &&
    python manage.py collectstatic --noinput &&
    gunicorn --bind 0.0.0.0:8000 --workers 1 --timeout 300 config.wsgi:application
  "
```

### 4. Оптимизировать обработку больших данных

Если проблема возникает при обработке большого количества документов (например, 25000+), рассмотрите:

- Использование пагинации
- Обработку данных порциями (batches)
- Увеличение таймаута для долгих запросов
- Использование async workers (gevent/eventlet) для I/O-bound операций

### 5. Проверить утечки памяти

```bash
# Мониторить использование памяти в реальном времени
docker stats --no-stream rag_web_backend

# Если память постоянно растет - возможна утечка
```

## Проблема: Backend не отображается или не запускается

### 1. Проверить статус контейнеров

```bash
# Проверить все контейнеры
docker-compose ps

# Или через docker
docker ps -a | grep rag_web

# Проверить логи backend
docker-compose logs backend

# Проверить логи с последними строками
docker-compose logs --tail=100 backend
```

### 2. Если `deploy.resources` не работает (ОБЯЗАТЕЛЬНО для обычного Docker Compose)

**ВАЖНО:** `deploy` работает ТОЛЬКО в Docker Swarm mode. Для обычного Docker Compose используйте `mem_limit`.

**Замените в `docker-compose.yml`:**

```yaml
# УДАЛИТЬ это (не работает без Swarm):
deploy:
  resources:
    limits:
      memory: 4G
    reservations:
      memory: 1G

# ДОБАВИТЬ это (работает всегда):
mem_limit: 4g
mem_reservation: 1g
```

Также убедитесь, что `depends_on` не использует `condition: service_healthy` (это тоже требует Swarm):

```yaml
# Заменить:
depends_on:
  backend:
    condition: service_healthy

# На:
depends_on:
  - backend
```

Затем:
```bash
docker-compose down
docker-compose up -d --build
```

### 3. Проверить ошибки при запуске

```bash
# Запустить в foreground для просмотра ошибок
docker-compose up backend

# Или посмотреть последние ошибки
docker-compose logs backend | grep -i error
docker-compose logs backend | tail -50
```

### 4. Проверить, что контейнер запущен

```bash
# Проверить процессы внутри контейнера
docker-compose exec backend ps aux

# Проверить, что Gunicorn работает
docker-compose exec backend ps aux | grep gunicorn

# Проверить порт внутри контейнера
docker-compose exec backend netstat -tlnp | grep 8000
```

### 5. Если контейнер падает сразу после запуска

```bash
# Проверить, что файлы на месте
docker-compose exec backend ls -la /app/test_final_v2.py /app/prompts.py

# Проверить импорты
docker-compose exec backend python -c "import test_final_v2; import prompts; print('OK')"

# Проверить .env файл
docker-compose exec backend env | grep DJANGO
```

### 6. Проверить, что backend отвечает

```bash
# Изнутри контейнера
docker-compose exec backend curl http://localhost:8000/api/query/

# С хоста
curl http://localhost:8000/api/query/
```

## Полная пересборка

Если ничего не помогает:

```bash
# Остановить и удалить все
docker compose down -v

# Удалить образы
docker images | grep rag_web | awk '{print $3}' | xargs docker rmi -f

# Пересобрать с нуля
docker compose build --no-cache
docker compose up -d

# Проверить логи
docker compose logs -f
```

