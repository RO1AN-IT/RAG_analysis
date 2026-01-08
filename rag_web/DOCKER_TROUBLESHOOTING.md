# Устранение неполадок Docker Compose

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

