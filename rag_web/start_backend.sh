#!/bin/bash
# Скрипт для запуска Django backend

cd "$(dirname "$0")/backend"

# Активация виртуального окружения, если оно существует
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Запуск Django сервера
python manage.py runserver

