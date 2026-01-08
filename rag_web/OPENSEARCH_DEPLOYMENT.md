# Развертывание OpenSearch на сервере

Эта инструкция поможет вам развернуть OpenSearch на сервере, где уже размещен ваш сайт.

## Содержание

1. [Варианты развертывания](#варианты-развертывания)
2. [Развертывание через Docker Compose (рекомендуется)](#развертывание-через-docker-compose-рекомендуется)
3. [Настройка backend для работы с OpenSearch](#настройка-backend-для-работы-с-opensearch)
4. [Миграция данных (если нужно)](#миграция-данных-если-нужно)
5. [Проверка работоспособности](#проверка-работоспособности)
6. [Безопасность и производительность](#безопасность-и-производительность)
7. [Устранение неполадок](#устранение-неполадок)

---

## Варианты развертывания

### Вариант 1: Docker Compose (рекомендуется) ✅
- Простота установки и управления
- Изоляция от системы
- Легкое обновление
- Автоматический перезапуск

### Вариант 2: Интеграция в существующий docker-compose.yml
- Если вы уже используете Docker для backend/frontend
- Все сервисы в одном файле

### Вариант 3: Ручная установка
- Больше контроля
- Требует больше настроек

**В этой инструкции мы рассмотрим Вариант 1 (Docker Compose) как наиболее простой и надежный.**

---

## Развертывание через Docker Compose (рекомендуется)

### 1. Предварительные требования

Убедитесь, что на сервере установлены Docker и Docker Compose:

```bash
# Проверить версию Docker
docker --version

# Проверить версию Docker Compose
docker compose version || docker-compose --version

# Если не установлены, установите:
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Для Docker Compose (если не установлен):
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Перелогиниться для применения группы docker
exit
# (заново подключиться по SSH)
```

### 2. Подготовка на сервере

```bash
# Перейти в директорию проекта
cd ~/projects/RAG_analysis/rag_web

# Проверить наличие файла docker-compose.opensearch.yml
ls -la docker-compose.opensearch.yml
```

### 3. Настройка конфигурации OpenSearch

Откройте файл `docker-compose.opensearch.yml` и при необходимости измените настройки:

```bash
nano docker-compose.opensearch.yml
```

**Важные настройки:**

1. **Память для OpenSearch** (строка 16):
   ```yaml
   - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
   ```
   - Минимум: `-Xms512m -Xmx512m` (512MB)
   - Рекомендуется: `-Xms1g -Xmx1g` (1GB)
   - Для больших индексов: `-Xms2g -Xmx2g` (2GB)
   - **Важно**: Не выделяйте больше 50% RAM сервера для OpenSearch

2. **Порты** (строки 28-29):
   ```yaml
   ports:
     - "0.0.0.0:9200:9200"  # OpenSearch API
     - "9600:9600"           # Performance Analyzer
   ```
   - Если OpenSearch на том же сервере, что и backend, можно использовать `127.0.0.1:9200:9200` для безопасности
   - Если нужен доступ извне, оставьте `0.0.0.0:9200:9200`

3. **Безопасность** (строка 13):
   ```yaml
   - plugins.security.disabled=true
   ```
   - `true` - без аутентификации (проще, но менее безопасно)
   - `false` - с аутентификацией (требует настройки паролей)

### 4. Запуск OpenSearch

```bash
# Перейти в директорию проекта
cd ~/projects/RAG_analysis/rag_web

# Запустить OpenSearch в фоновом режиме
docker compose -f docker-compose.opensearch.yml up -d

# Или если используется docker-compose (старая версия):
docker-compose -f docker-compose.opensearch.yml up -d

# Проверить статус
docker compose -f docker-compose.opensearch.yml ps

# Посмотреть логи
docker compose -f docker-compose.opensearch.yml logs -f
```

### 5. Проверка запуска

```bash
# Проверить, что контейнер запущен
docker ps | grep opensearch

# Проверить доступность OpenSearch API
curl http://localhost:9200

# Должен вернуться JSON с информацией о кластере
```

**Ожидаемый ответ:**
```json
{
  "name": "opensearch-node1",
  "cluster_name": "docker-cluster",
  "cluster_uuid": "...",
  "version": {
    "number": "2.11.0",
    ...
  }
}
```

### 6. Настройка автозапуска

Docker Compose автоматически перезапускает контейнеры при перезагрузке сервера (благодаря `restart: unless-stopped` в конфигурации).

Для проверки:
```bash
# Перезагрузить сервер (осторожно!)
sudo reboot

# После перезагрузки проверить, что OpenSearch запустился
docker ps | grep opensearch
```

---

## Настройка backend для работы с OpenSearch

### 1. Определить адрес OpenSearch

**Если OpenSearch на том же сервере, что и backend:**
- `OPENSEARCH_HOST=localhost` или `127.0.0.1`
- `OPENSEARCH_PORT=9200`

**Если OpenSearch на другом сервере:**
- `OPENSEARCH_HOST=<IP-адрес-сервера>` или `<доменное-имя>`
- `OPENSEARCH_PORT=9200`

### 2. Обновить переменные окружения backend

```bash
# Перейти в директорию backend
cd ~/projects/RAG_analysis/rag_web/backend

# Открыть файл .env
nano .env
```

**Добавить или обновить следующие переменные:**

```env
# OpenSearch настройки
OPENSEARCH_HOST=localhost  # или IP адрес сервера OpenSearch
OPENSEARCH_PORT=9200
OPENSEARCH_USE_SSL=False  # False для docker-compose без SSL
OPENSEARCH_VERIFY_CERTS=False

# Аутентификация OpenSearch (если plugins.security.disabled=false)
# Если plugins.security.disabled=true, оставьте пустыми:
OPENSEARCH_AUTH_USERNAME=
OPENSEARCH_AUTH_PASSWORD=
```

**Если OpenSearch с аутентификацией:**
```env
OPENSEARCH_AUTH_USERNAME=admin
OPENSEARCH_AUTH_PASSWORD=your-password-here
```

### 3. Перезапустить backend

**Если используете systemd (Gunicorn):**
```bash
sudo systemctl restart rag_web
sudo systemctl status rag_web
```

**Если используете Docker Compose:**
```bash
cd ~/projects/RAG_analysis/rag_web
docker compose restart backend
docker compose logs backend
```

### 4. Проверить подключение из backend

```bash
# Зайти в контейнер backend (если Docker) или активировать venv
cd ~/projects/RAG_analysis/rag_web/backend
source venv/bin/activate  # если не Docker

# Проверить подключение через Python
python manage.py shell
```

В Python shell:
```python
import os
from opensearchpy import OpenSearch

host = os.environ.get('OPENSEARCH_HOST', 'localhost')
port = int(os.environ.get('OPENSEARCH_PORT', 9200))
use_ssl = os.environ.get('OPENSEARCH_USE_SSL', 'False').lower() == 'true'

client = OpenSearch(
    hosts=[{'host': host, 'port': port}],
    use_ssl=use_ssl,
    verify_certs=False
)

# Проверить подключение
if client.ping():
    print("✓ Подключение к OpenSearch успешно!")
    print(f"Версия: {client.info()['version']['number']}")
else:
    print("❌ Не удалось подключиться к OpenSearch")
```

---

## Миграция данных (если нужно)

Если у вас уже есть данные в OpenSearch на другом сервере или локально, используйте скрипты экспорта/импорта.

### 1. Экспорт данных со старого сервера

**На старом сервере (или локально):**

```bash
cd ~/projects/RAG_analysis/rag_web

# Установить зависимости для скриптов (если еще не установлены)
pip install opensearch-py

# Настроить переменные окружения для экспорта
export OPENSEARCH_HOST=old-server-ip
export OPENSEARCH_PORT=9200
export OPENSEARCH_USERNAME=admin  # если нужна аутентификация
export OPENSEARCH_PASSWORD=old-password  # если нужна аутентификация

# Запустить экспорт
python export_opensearch.py
```

Скрипт создаст директорию `opensearch_export/` с файлами:
- `rag_descriptions_export.json`
- `rag_layers_export.json`

### 2. Копирование данных на новый сервер

```bash
# На старом сервере: создать архив
cd ~/projects/RAG_analysis/rag_web
tar -czf opensearch_export.tar.gz opensearch_export/

# Скопировать на новый сервер (с локального компьютера)
scp user@old-server:/path/to/opensearch_export.tar.gz ./
scp opensearch_export.tar.gz user@new-server:/home/user/

# Или через rsync
rsync -avz opensearch_export/ user@new-server:/home/user/projects/RAG_analysis/rag_web/opensearch_export/
```

### 3. Импорт данных на новый сервер

**На новом сервере:**

```bash
cd ~/projects/RAG_analysis/rag_web

# Распаковать архив (если использовали tar)
tar -xzf opensearch_export.tar.gz

# Установить зависимости (если еще не установлены)
pip install opensearch-py

# Настроить переменные окружения для импорта
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
export OPENSEARCH_USE_SSL=False
export OPENSEARCH_VERIFY_CERTS=False
# Если нужна аутентификация:
# export OPENSEARCH_USERNAME=admin
# export OPENSEARCH_PASSWORD=password

# Запустить импорт
python import_opensearch.py
```

Скрипт запросит подтверждение перед импортом.

### 4. Проверка импортированных данных

```bash
# Проверить индексы
curl http://localhost:9200/_cat/indices?v

# Проверить количество документов в индексе
curl http://localhost:9200/rag_descriptions/_count
curl http://localhost:9200/rag_layers/_count
```

---

## Проверка работоспособности

### 1. Проверка OpenSearch

```bash
# Проверить статус контейнера
docker compose -f docker-compose.opensearch.yml ps

# Проверить логи
docker compose -f docker-compose.opensearch.yml logs --tail=50

# Проверить API
curl http://localhost:9200

# Проверить индексы
curl http://localhost:9200/_cat/indices?v

# Проверить здоровье кластера
curl http://localhost:9200/_cluster/health?pretty
```

### 2. Проверка подключения из backend

```bash
# Проверить логи backend на ошибки подключения
sudo journalctl -u rag_web -n 50 | grep -i opensearch

# Или если Docker:
docker compose logs backend | grep -i opensearch

# Сделать тестовый запрос к API
curl http://your-domain.com/api/query/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"query": "тестовый запрос"}'
```

### 3. Проверка OpenSearch Dashboards (опционально)

Если вы запустили OpenSearch Dashboards (порт 5601):

```bash
# Проверить доступность
curl http://localhost:5601

# Открыть в браузере (если порт открыт)
# http://your-server-ip:5601
```

**Важно**: По умолчанию Dashboards доступен только на localhost. Для доступа извне нужно настроить Nginx reverse proxy или изменить настройки безопасности.

---

## Безопасность и производительность

### 1. Безопасность

#### Ограничение доступа к порту 9200

**Если OpenSearch на том же сервере, что и backend:**

Измените в `docker-compose.opensearch.yml`:
```yaml
ports:
  - "127.0.0.1:9200:9200"  # Только localhost
```

**Если нужен доступ извне:**

Настройте файрвол:
```bash
# Разрешить доступ только с определенного IP
sudo ufw allow from <backend-server-ip> to any port 9200

# Или разрешить только с вашего IP
sudo ufw allow from <your-ip> to any port 9200
```

#### Включение аутентификации (рекомендуется для продакшена)

1. Измените `docker-compose.opensearch.yml`:
```yaml
environment:
  - discovery.type=single-node
  - plugins.security.disabled=false
  - OPENSEARCH_INITIAL_ADMIN_PASSWORD=your-strong-password-here
```

2. Обновите `.env` в backend:
```env
OPENSEARCH_AUTH_USERNAME=admin
OPENSEARCH_AUTH_PASSWORD=your-strong-password-here
```

3. Перезапустите:
```bash
docker compose -f docker-compose.opensearch.yml down
docker compose -f docker-compose.opensearch.yml up -d
```

### 2. Производительность

#### Настройка памяти

Проверьте доступную память:
```bash
free -h
```

Рекомендации:
- Минимум: 512MB для OpenSearch
- Рекомендуется: 1-2GB для OpenSearch
- Не выделяйте больше 50% RAM сервера

Измените в `docker-compose.opensearch.yml`:
```yaml
- OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g  # Для сервера с 4GB+ RAM
```

#### Настройка диска

OpenSearch требует быстрого диска. Для продакшена рекомендуется:
- SSD диск
- Отдельный том для данных OpenSearch

В `docker-compose.opensearch.yml` уже настроен volume:
```yaml
volumes:
  - opensearch-data:/usr/share/opensearch/data
```

#### Мониторинг ресурсов

```bash
# Использование памяти
docker stats opensearch

# Использование диска
docker system df

# Логи производительности
docker compose -f docker-compose.opensearch.yml logs | grep -i performance
```

---

## Устранение неполадок

### Проблема: OpenSearch не запускается

```bash
# Проверить логи
docker compose -f docker-compose.opensearch.yml logs

# Частые причины:
# 1. Недостаточно памяти
free -h
# Решение: уменьшите OPENSEARCH_JAVA_OPTS

# 2. Порт 9200 уже занят
sudo netstat -tlnp | grep 9200
# Решение: остановите другой сервис или измените порт

# 3. Проблемы с правами доступа
docker compose -f docker-compose.opensearch.yml down -v
docker compose -f docker-compose.opensearch.yml up -d
```

### Проблема: Конфликт имени контейнера

**Ошибка:** `Error response from daemon: Conflict. The container name "/opensearch" is already in use`

**Решение:**

```bash
# Вариант 1: Остановить и удалить старый контейнер через docker-compose
docker compose -f docker-compose.opensearch.yml down
docker compose -f docker-compose.opensearch.yml up -d

# Вариант 2: Если docker-compose не работает, удалить контейнер вручную
# Сначала проверить существующие контейнеры
docker ps -a | grep opensearch

# Остановить старый контейнер
docker stop opensearch
docker stop opensearch-dashboards

# Удалить старые контейнеры
docker rm opensearch
docker rm opensearch-dashboards

# Теперь запустить заново
docker compose -f docker-compose.opensearch.yml up -d

# Вариант 3: Удалить все остановленные контейнеры (если их много)
docker container prune -f

# Затем запустить заново
docker compose -f docker-compose.opensearch.yml up -d
```

**Важно:** Если в старом контейнере есть важные данные, сначала сделайте экспорт:
```bash
# Экспорт данных перед удалением
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
python export_opensearch.py
```

### Проблема: Backend не может подключиться к OpenSearch

```bash
# 1. Проверить, что OpenSearch запущен
docker ps | grep opensearch

# 2. Проверить доступность с сервера
curl http://localhost:9200

# 3. Проверить переменные окружения backend
cd ~/projects/RAG_analysis/rag_web/backend
cat .env | grep OPENSEARCH

# 4. Проверить логи backend
sudo journalctl -u rag_web -n 100 | grep -i opensearch
```

### Проблема: Недостаточно памяти

```bash
# Проверить использование памяти
free -h
docker stats opensearch

# Уменьшить выделенную память в docker-compose.opensearch.yml
# Изменить -Xms1g -Xmx1g на -Xms512m -Xmx512m
nano docker-compose.opensearch.yml

# Перезапустить
docker compose -f docker-compose.opensearch.yml restart
```

### Проблема: Медленные запросы

```bash
# Проверить использование ресурсов
docker stats opensearch
htop

# Проверить размер индексов
curl http://localhost:9200/_cat/indices?v

# Проверить здоровье кластера
curl http://localhost:9200/_cluster/health?pretty

# Возможные решения:
# 1. Увеличить память для OpenSearch
# 2. Оптимизировать индексы
# 3. Использовать SSD диск
```

### Проблема: Данные не импортируются

```bash
# Проверить логи импорта
python import_opensearch.py

# Проверить формат файлов экспорта
ls -lh opensearch_export/
cat opensearch_export/rag_descriptions_export.json | head -20

# Проверить подключение к OpenSearch
curl http://localhost:9200

# Проверить права доступа к файлам
ls -la opensearch_export/
```

---

## Полезные команды

### Управление OpenSearch

```bash
# Запустить
docker compose -f docker-compose.opensearch.yml up -d

# Остановить
docker compose -f docker-compose.opensearch.yml stop

# Остановить и удалить контейнеры
docker compose -f docker-compose.opensearch.yml down

# Остановить и удалить контейнеры + данные (ОСТОРОЖНО!)
docker compose -f docker-compose.opensearch.yml down -v

# Перезапустить
docker compose -f docker-compose.opensearch.yml restart

# Посмотреть логи
docker compose -f docker-compose.opensearch.yml logs -f

# Посмотреть статус
docker compose -f docker-compose.opensearch.yml ps
```

### Работа с индексами

```bash
# Список всех индексов
curl http://localhost:9200/_cat/indices?v

# Информация об индексе
curl http://localhost:9200/rag_descriptions?pretty

# Количество документов в индексе
curl http://localhost:9200/rag_descriptions/_count

# Удалить индекс (ОСТОРОЖНО!)
curl -X DELETE http://localhost:9200/rag_descriptions

# Создать индекс заново (после удаления)
# Используйте import_opensearch.py
```

### Мониторинг

```bash
# Использование ресурсов контейнера
docker stats opensearch

# Здоровье кластера
curl http://localhost:9200/_cluster/health?pretty

# Статистика узла
curl http://localhost:9200/_nodes/stats?pretty

# Использование диска
docker system df -v
```

---

## Резервное копирование

### Автоматическое резервное копирование

Создайте скрипт для регулярного бэкапа:

```bash
nano ~/backup_opensearch.sh
```

Содержимое:
```bash
#!/bin/bash
BACKUP_DIR=~/backups/opensearch
DATE=$(date +%Y%m%d_%H%M%S)
PROJECT_DIR=~/projects/RAG_analysis/rag_web

mkdir -p $BACKUP_DIR

cd $PROJECT_DIR

# Экспорт данных
export OPENSEARCH_HOST=localhost
export OPENSEARCH_PORT=9200
export OPENSEARCH_USE_SSL=False

python export_opensearch.py

# Архивировать экспортированные данные
tar -czf $BACKUP_DIR/opensearch_backup_$DATE.tar.gz opensearch_export/

# Удалить старые бэкапы (старше 30 дней)
find $BACKUP_DIR -name "opensearch_backup_*.tar.gz" -mtime +30 -delete

echo "Бэкап создан: $BACKUP_DIR/opensearch_backup_$DATE.tar.gz"
```

Сделать исполняемым:
```bash
chmod +x ~/backup_opensearch.sh
```

Добавить в crontab (ежедневно в 2:00):
```bash
crontab -e
# Добавить строку:
0 2 * * * /home/user/backup_opensearch.sh >> /home/user/backups/opensearch_backup.log 2>&1
```

---

## Интеграция с существующим docker-compose.yml

Если вы хотите запускать OpenSearch вместе с backend и frontend в одном файле:

1. Откройте `docker-compose.yml`
2. Добавьте сервис OpenSearch из `docker-compose.opensearch.yml`
3. Обновите сеть, чтобы backend мог подключиться к OpenSearch

Пример:
```yaml
services:
  opensearch:
    image: opensearchproject/opensearch:2.11.0
    container_name: opensearch
    environment:
      - discovery.type=single-node
      - plugins.security.disabled=true
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
    volumes:
      - opensearch-data:/usr/share/opensearch/data
    ports:
      - "127.0.0.1:9200:9200"
    networks:
      - rag_network
    restart: unless-stopped

  backend:
    # ... существующая конфигурация ...
    environment:
      - OPENSEARCH_HOST=opensearch  # Имя сервиса в Docker сети
      - OPENSEARCH_PORT=9200
    depends_on:
      - opensearch
    networks:
      - rag_network

volumes:
  opensearch-data:
```

Затем в `.env` backend:
```env
OPENSEARCH_HOST=opensearch  # Имя сервиса в Docker
```

---

## Заключение

После выполнения всех шагов у вас должно быть:

✅ OpenSearch запущен и доступен  
✅ Backend настроен и подключается к OpenSearch  
✅ Данные импортированы (если нужно)  
✅ Все работает и проверено  

**Следующие шаги:**
1. Настроить регулярное резервное копирование
2. Настроить мониторинг (опционально)
3. Включить аутентификацию для продакшена (рекомендуется)
4. Оптимизировать производительность под вашу нагрузку

**Полезные ссылки:**
- [Документация OpenSearch](https://opensearch.org/docs/)
- [Docker Compose документация](https://docs.docker.com/compose/)

---

**Примечание**: Если у вас возникли проблемы, проверьте раздел [Устранение неполадок](#устранение-неполадок) или логи OpenSearch и backend.

