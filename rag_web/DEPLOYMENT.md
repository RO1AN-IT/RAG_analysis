# Инструкция по размещению проекта на сервере

## Предварительные требования

### 1. Системные требования

- **ОС**: Ubuntu 20.04/22.04 или Debian 11/12 (рекомендуется)
- **RAM**: минимум 4GB (рекомендуется 8GB+)
- **Диск**: минимум 20GB свободного места
- **Процессор**: 2+ ядра

### 2. Установка системных зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка базовых инструментов
sudo apt install -y git curl wget build-essential

# Установка Python 3.11+
sudo apt install -y python3.11 python3.11-venv python3-pip

# Установка Node.js 18+ и npm
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Установка Nginx
sudo apt install -y nginx

# Установка PostgreSQL (опционально, если нужна БД)
sudo apt install -y postgresql postgresql-contrib

# Установка Docker и Docker Compose (для OpenSearch, если нужно)
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER
```

## Подготовка сервера

### 1. Создание пользователя для приложения (рекомендуется)

```bash
# Создать пользователя
sudo adduser ragapp

# Добавить в группу sudo (опционально)
sudo usermod -aG sudo ragapp

# Переключиться на пользователя
su - ragapp

# Для выхода из пользователя ragapp выполните:
exit

# Для удаления пользователя ragapp (если нужно):
sudo deluser ragapp
# Удалить домашнюю директорию пользователя (опционально):
sudo deluser --remove-home ragapp
```

### 2. Настройка SSH ключей

На локальном компьютере:

```bash
# Генерация SSH ключа (если еще нет)
ssh-keygen -t ed25519 -C "your_email@example.com"

# Копирование ключа на сервер
ssh-copy-id ragapp@your-server-ip
```

### 3. Настройка файрвола

```bash
# Разрешить SSH
sudo ufw allow 22/tcp

# Разрешить HTTP и HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Включить файрвол
sudo ufw enable
sudo ufw status
```

## Размещение проекта на сервере

### Вариант 1: Использование Git (рекомендуется)

```bash
# Переключиться на пользователя приложения
su - ragapp

# Создать директорию для проекта
mkdir -p ~/projects
cd ~/projects

# Клонировать репозиторий
git clone https://github.com/your-username/RAG_analysis.git
cd RAG_analysis/rag_web
```

### Вариант 2: Использование rsync/SCP

На локальном компьютере:

```bash
# Использовать скрипт transfer_to_server.sh
cd /path/to/RAG_analysis
./rag_web/transfer_to_server.sh ragapp@your-server-ip /home/ragapp/projects
```

Или вручную:

```bash
rsync -avz --progress \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.pyc' \
    --exclude='.env' \
    ./rag_web/ ragapp@your-server-ip:/home/ragapp/projects/RAG_analysis/rag_web/
```

## Настройка Backend (Django)

### 1. Создание виртуального окружения

```bash
cd ~/projects/RAG_analysis/rag_web/backend

# Создать виртуальное окружение
python3.11 -m venv venv

# Активировать виртуальное окружение
source venv/bin/activate

# Обновить pip
pip install --upgrade pip
```

### 2. Установка зависимостей

```bash
# Установить зависимости
pip install -r requirements.txt

# Если есть проблемы с зависимостями, установить отдельно:
pip install Django>=4.2.0
pip install django-cors-headers>=4.0.0
pip install pandas>=2.0.0
pip install opensearch-py>=2.0.0
pip install sentence-transformers>=2.2.0
pip install gigachat>=0.1.0
pip install duckdb>=0.8.0
pip install langchain-core>=0.1.0
pip install requests>=2.31.0
pip install python-dotenv>=1.0.0
pip install gunicorn>=21.2.0
```

### 3. Настройка переменных окружения

```bash
# Создать .env файл
cp env.example .env
nano .env
```

Заполните следующие переменные:

```env
# Django настройки
DJANGO_SECRET_KEY=s8d0a^2osjnbp9n7hzc@&9r!_c@#_-ha1np2@(69e-b@la^894
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=your-domain.com,www.your-domain.com,server-ip

# OpenSearch настройки (IP вашего OpenSearch сервера)
OPENSEARCH_HOST=155.212.191.208
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=False
OPENSEARCH_VERIFY_CERTS=False
OPENSEARCH_AUTH_USERNAME=admin
OPENSEARCH_AUTH_PASSWORD=admin

# GigaChat учетные данные
GIGACHAT_CREDENTIALS=your-gigachat-credentials

# HeyGen настройки
HEYGEN_API_KEY=your-heygen-api-key
HEYGEN_AVATAR_ID=Katya_Chair_Sitting_public
HEYGEN_VOICE_ID=453c20e1525a429080e2ad9e4b26f2cd

# CORS настройки
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

**Сгенерировать SECRET_KEY:**

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 4. Выполнение миграций

```bash
# Активировать venv
source venv/bin/activate

# Выполнить миграции
python manage.py migrate

# Создать суперпользователя (опционально)
python manage.py createsuperuser
```

### 5. Сборка статических файлов

```bash
python manage.py collectstatic --noinput
```

## Настройка Frontend (React)

### 1. Установка зависимостей

```bash
cd ~/projects/RAG_analysis/rag_web/frontend

# Установить зависимости
npm install
```

### 2. Создание production build

```bash
# Создать production build
npm run build

# Проверить, что build создан
ls -la build/
```

## Настройка Nginx

### 1. Создание конфигурации Nginx

```bash
sudo nano /etc/nginx/sites-available/rag_web
```

Содержимое конфигурации:

```nginx
# Frontend (React)
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Корневая директория для React build
    root /home/ragapp/projects/RAG_analysis/rag_web/frontend/build;
    index index.html;

    # Логирование
    access_log /var/log/nginx/rag_web_access.log;
    error_log /var/log/nginx/rag_web_error.log;

    # Статические файлы React
    location / {
        try_files $uri $uri/ /index.html;
        add_header Cache-Control "no-cache";
    }

    # Кэширование статических ресурсов
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Проксирование API запросов к Django
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    # Проксирование запросов к HeyGen API (если нужно)
    location /api/heygen/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

### 2. Активация конфигурации

```bash
# Создать символическую ссылку
sudo ln -s /etc/nginx/sites-available/rag_web /etc/nginx/sites-enabled/

# Удалить дефолтную конфигурацию (опционально)
sudo rm /etc/nginx/sites-enabled/default

# Проверить конфигурацию
sudo nginx -t

# Перезагрузить Nginx
sudo systemctl reload nginx
```

## Настройка Gunicorn

### 1. Создание systemd сервиса для Gunicorn

```bash
sudo nano /etc/systemd/system/rag_web.service
```

Содержимое файла:

```ini
[Unit]
Description=Gunicorn instance to serve RAG Web Django application
After=network.target

[Service]
User=ragapp
Group=www-data
WorkingDirectory=/home/ragapp/projects/RAG_analysis/rag_web/backend
Environment="PATH=/home/ragapp/projects/RAG_analysis/rag_web/backend/venv/bin"
ExecStart=/home/ragapp/projects/RAG_analysis/rag_web/backend/venv/bin/gunicorn \
    --workers 3 \
    --bind 127.0.0.1:8000 \
    --timeout 120 \
    --access-logfile /var/log/gunicorn/rag_web_access.log \
    --error-logfile /var/log/gunicorn/rag_web_error.log \
    config.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 2. Создание директории для логов

```bash
sudo mkdir -p /var/log/gunicorn
sudo chown ragapp:www-data /var/log/gunicorn
```

### 3. Запуск и автозагрузка Gunicorn

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Запустить сервис
sudo systemctl start rag_web

# Включить автозагрузку
sudo systemctl enable rag_web

# Проверить статус
sudo systemctl status rag_web

# Просмотр логов
sudo journalctl -u rag_web -f
```

## Настройка SSL (Let's Encrypt)

### 1. Установка Certbot

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### 2. Получение SSL сертификата

```bash
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

Certbot автоматически обновит конфигурацию Nginx.

### 3. Автоматическое обновление сертификата

```bash
# Проверить автоматическое обновление
sudo certbot renew --dry-run
```

## Управление приложением

### Команды для управления сервисом

```bash
# Перезапуск Django приложения
sudo systemctl restart rag_web

# Остановка
sudo systemctl stop rag_web

# Старт
sudo systemctl start rag_web

# Статус
sudo systemctl status rag_web

# Логи
sudo journalctl -u rag_web -f
```

### Обновление кода

```bash
# Переключиться на пользователя
su - ragapp

# Перейти в директорию проекта
cd ~/projects/RAG_analysis

# Получить последние изменения
git pull origin main

# Backend: обновить зависимости и миграции
cd rag_web/backend
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart rag_web

# Frontend: пересобрать
cd ../frontend
npm install
npm run build
sudo systemctl reload nginx
```

## Мониторинг и логи

### Просмотр логов

```bash
# Логи Gunicorn
sudo tail -f /var/log/gunicorn/rag_web_error.log
sudo tail -f /var/log/gunicorn/rag_web_access.log

# Логи Nginx
sudo tail -f /var/log/nginx/rag_web_error.log
sudo tail -f /var/log/nginx/rag_web_access.log

# Логи systemd
sudo journalctl -u rag_web -f
```

### Проверка процессов

```bash
# Проверить, что Gunicorn запущен
ps aux | grep gunicorn

# Проверить, что Nginx запущен
sudo systemctl status nginx

# Проверить открытые порты
sudo netstat -tlnp | grep -E ':(80|443|8000)'
```

## Резервное копирование

### Создание бэкапа

```bash
# Создать директорию для бэкапов
mkdir -p ~/backups

# Бэкап базы данных (если используется)
# pg_dump your_database > ~/backups/db_backup_$(date +%Y%m%d).sql

# Бэкап проекта
tar -czf ~/backups/rag_web_backup_$(date +%Y%m%d).tar.gz \
    ~/projects/RAG_analysis/rag_web \
    --exclude='venv' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='*.pyc'
```

### Автоматическое резервное копирование (cron)

```bash
# Добавить в crontab
crontab -e

# Бэкап каждый день в 2:00
0 2 * * * /home/ragapp/backup_script.sh
```

## Устранение неполадок

### Проблема: 502 Bad Gateway

```bash
# Проверить, запущен ли Gunicorn
sudo systemctl status rag_web

# Проверить логи
sudo journalctl -u rag_web -n 50

# Проверить, слушает ли порт 8000
sudo netstat -tlnp | grep 8000
```

### Проблема: 403 Forbidden

```bash
# Проверить права доступа
sudo chown -R ragapp:www-data ~/projects/RAG_analysis/rag_web
sudo chmod -R 755 ~/projects/RAG_analysis/rag_web/frontend/build
```

### Проблема: Статические файлы не загружаются

```bash
# Пересобрать статические файлы
cd ~/projects/RAG_analysis/rag_web/backend
source venv/bin/activate
python manage.py collectstatic --noinput
```

### Проблема: No space left on device (закончилось место на диске)

**Быстрое решение:**

```bash
# 1. Проверить использование диска
df -h

# 2. Очистить кэш apt (освободит обычно 500MB-2GB)
sudo apt clean
sudo apt autoremove -y

# 3. Очистить системные логи (освободит обычно 500MB-1GB)
sudo journalctl --vacuum-time=7d
sudo journalctl --vacuum-size=500M

# 4. Очистить pip кэш (особенно важно после неудачной установки torch)
pip cache purge
# Или:
python3 -m pip cache purge

# 5. Проверить результат
df -h
```

**Дополнительная очистка:**

```bash
# Найти большие файлы и директории
du -sh /* 2>/dev/null | sort -hr | head -20
du -sh ~/* 2>/dev/null | sort -hr | head -20

# Найти и удалить старые файлы логов
sudo find /var/log -type f -name "*.log" -mtime +30 -delete
sudo find /var/log -type f -name "*.gz" -delete

# Очистить npm кэш (для frontend)
npm cache clean --force

# Найти большие виртуальные окружения
find ~ -type d -name "venv" -o -name "node_modules" | xargs du -sh 2>/dev/null | sort -hr

# Удалить ненужные Docker образы и контейнеры (если используется Docker)
docker system prune -a --volumes

# Найти файлы больше 100MB
find ~ -type f -size +100M 2>/dev/null | head -20
```

**Если torch не устанавливается из-за нехватки места:**

Torch занимает ~900MB, поэтому нужно минимум 2-3GB свободного места. Варианты решения:

1. **Расширить диск сервера** (если возможно)

2. **Установить torch отдельно с очисткой кэша:**
   ```bash
   # Очистить все кэши перед установкой
   pip cache purge
   sudo apt clean
   
   # Установить torch отдельно (займет ~900MB)
   pip install torch --no-cache-dir
   
   # Затем установить остальные зависимости
   pip install -r requirements.txt --no-cache-dir
   ```

3. **Использовать более легкую версию torch (CPU-only):**
   ```bash
   pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
   ```

4. **Установить зависимости поэтапно:**
   ```bash
   # Сначала установить основные зависимости
   pip install Django django-cors-headers pandas opensearch-py requests python-dotenv gunicorn --no-cache-dir
   
   # Затем torch (самый тяжелый)
   pip install torch --no-cache-dir
   
   # Затем остальное
   pip install sentence-transformers gigachat duckdb langchain-core --no-cache-dir
   ```

### Проблема: Ошибки подключения к OpenSearch

```bash
# Проверить доступность OpenSearch сервера
curl http://155.212.191.208:9200

# Проверить переменные окружения
cd ~/projects/RAG_analysis/rag_web/backend
source venv/bin/activate
python manage.py shell
>>> import os
>>> from django.conf import settings
>>> print(os.environ.get('OPENSEARCH_HOST'))
```

## Безопасность

### Рекомендации по безопасности

1. **Регулярные обновления**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Настройка fail2ban**:
   ```bash
   sudo apt install -y fail2ban
   sudo systemctl enable fail2ban
   sudo systemctl start fail2ban
   ```

3. **Защита .env файла**:
   ```bash
   chmod 600 ~/projects/RAG_analysis/rag_web/backend/.env
   ```

4. **Регулярное резервное копирование**

5. **Мониторинг логов на подозрительную активность**

## Проверка работоспособности

После развертывания проверьте:

1. Frontend доступен: `http://your-domain.com`
2. API работает: `http://your-domain.com/api/`
3. Статические файлы загружаются
4. SSL сертификат работает: `https://your-domain.com`
5. Логи не содержат ошибок

## Полезные команды

```bash
# Перезапуск всех сервисов
sudo systemctl restart rag_web nginx

# Проверка конфигурации Nginx
sudo nginx -t

# Проверка использования ресурсов
htop
df -h
free -h

# Просмотр активных соединений
sudo netstat -tulpn
```

---

**Примечание**: Замените `your-domain.com` и `your-server-ip` на ваши реальные значения.

