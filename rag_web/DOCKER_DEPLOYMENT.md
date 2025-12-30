# Развертывание через Docker Compose

## Почему Docker Compose лучше?

### ✅ Преимущества Docker Compose:

1. **Простота запуска**
   - Одна команда запускает всё: `docker-compose up -d`
   - Не нужно настраивать systemd, nginx конфиги, виртуальные окружения вручную

2. **Изоляция зависимостей**
   - Каждый сервис работает в своей изолированной среде
   - Нет конфликтов версий Python/Node.js с системными пакетами
   - Легко удалить всё: `docker-compose down`

3. **Воспроизводимость**
   - Одинаковая среда на любом сервере
   - Легко перенести проект на другой сервер
   - Не нужно помнить все шаги настройки

4. **Легкое обновление**
   - Обновить код: `git pull && docker-compose up -d --build`
   - Откат: `docker-compose down && git checkout <previous-commit> && docker-compose up -d --build`

5. **Автоматическая настройка сети**
   - Сервисы автоматически видят друг друга по именам (backend, frontend)
   - Не нужно настраивать проксирование вручную

6. **Логи и мониторинг**
   - Все логи в одном месте: `docker-compose logs`
   - Легко следить за работой: `docker-compose logs -f`

7. **Масштабируемость**
   - Легко запустить несколько копий: `docker-compose up -d --scale backend=3`
   - Можно добавить Redis, PostgreSQL и другие сервисы

8. **Безопасность**
   - Изоляция процессов
   - Легко настроить ограничения ресурсов
   - Контейнеры работают от непривилегированных пользователей

9. **Отсутствие "загрязнения" системы**
   - Не устанавливаются пакеты в системные директории
   - Легко полностью удалить проект

10. **Упрощенная отладка**
    - Зайти в контейнер: `docker-compose exec backend bash`
    - Перезапустить один сервис: `docker-compose restart backend`
    - Посмотреть статус: `docker-compose ps`

## Установка Docker и Docker Compose

### На сервере:

```bash
# Обновить систему
sudo apt update && sudo apt upgrade -y

# Установить Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавить пользователя в группу docker
sudo usermod -aG docker $USER

# Проверить версию Docker
docker --version

# Проверить Docker Compose (может быть docker compose или docker-compose)
docker compose version || docker-compose --version

# Если docker compose не работает, установить docker-compose отдельно:
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version

# Перелогиниться для применения группы docker
exit
# (заново подключиться по SSH)
```

## Развертывание

### 1. Подготовка на сервере

```bash
# Клонировать репозиторий
cd ~
git clone https://github.com/your-username/RAG_analysis.git
cd RAG_analysis/rag_web

# Создать .env файл для backend
cp backend/env.example backend/.env
nano backend/.env
# Заполнить все необходимые переменные
```

### 2. Запуск

```bash
# Проверить, какая команда работает
docker compose version || docker-compose --version

# Если работает docker compose (новая версия):
docker compose up -d --build
docker compose ps
docker compose logs -f
docker compose down
docker compose down -v

# Если работает docker-compose (старая версия):
docker-compose up -d --build
docker-compose ps
docker-compose logs -f
docker-compose down
docker-compose down -v

# ВНИМАНИЕ: В дальнейших примерах используется docker compose
# Если у вас docker-compose, замените все "docker compose" на "docker-compose"
```

### 3. Управление

```bash
# Перезапустить все сервисы
docker compose restart

# Перезапустить только backend
docker compose restart backend

# Обновить код и пересобрать
git pull
docker compose up -d --build

# Посмотреть логи
docker compose logs backend
docker compose logs frontend
docker compose logs -f  # следить в реальном времени

# Зайти в контейнер backend
docker compose exec backend bash

# Выполнить команду в контейнере
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py migrate
```

### 4. Обновление проекта

```bash
# Получить последние изменения
git pull

# Пересобрать и перезапустить
docker compose up -d --build

# Или только перезапустить без пересборки (если код изменился, но Dockerfile не менялся)
docker compose up -d
```

## Проверка работоспособности

```bash
# Проверить, что контейнеры запущены
docker compose ps

# Проверить, что backend отвечает
curl http://localhost:8000/api/

# Проверить, что frontend отвечает
curl http://localhost/

# Проверить логи на ошибки
docker compose logs | grep -i error
```

## Файловая структура

```
rag_web/
├── docker-compose.yml          # Конфигурация всех сервисов
├── Dockerfile.backend          # Dockerfile для Django
├── Dockerfile.frontend         # Dockerfile для React
├── .dockerignore              # Файлы, которые не копировать в Docker
├── docker/
│   └── nginx.conf             # Конфигурация Nginx для frontend
├── backend/
│   ├── .env                   # Переменные окружения (НЕ коммитить!)
│   └── ...
└── frontend/
    └── ...
```

## Важные моменты

1. **Файл .env** должен быть создан на сервере, но НЕ должен быть в Git
2. **База данных** будет внутри контейнера - для продакшена лучше использовать внешнюю БД
3. **Статические файлы** собираются при запуске контейнера
4. **Миграции** выполняются автоматически при запуске

## Сравнение с предыдущим подходом

| Аспект | Nginx + Gunicorn + systemd | Docker Compose |
|--------|----------------------------|----------------|
| Установка зависимостей | Вручную на систему | Автоматически в контейнерах |
| Настройка | Много шагов, конфигов | Один файл docker-compose.yml |
| Изоляция | Зависит от системы | Полная изоляция |
| Переносимость | Сложная | Очень простая |
| Обновление | Много команд | Одна команда |
| Удаление | Сложно, много файлов | `docker-compose down -v` |
| Логи | Разбросаны по системе | `docker compose logs` |
| Отладка | Нужно знать систему | Простые команды Docker |

## Дополнительные возможности

### Добавить базу данных PostgreSQL:

```yaml
services:
  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: rag_db
      POSTGRES_USER: rag_user
      POSTGRES_PASSWORD: your_password

volumes:
  postgres_data:
```

### Добавить Redis:

```yaml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
```

### Настроить ограничения ресурсов:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

---

**Итого:** Docker Compose делает развертывание простым, воспроизводимым и легким в поддержке!

