#!/bin/bash
# Скрипт для запуска React frontend

# Устанавливаем TMPDIR для избежания ошибок с несуществующими путями
export TMPDIR=/tmp

cd "$(dirname "$0")/frontend"

# Установка зависимостей, если node_modules не существует
if [ ! -d "node_modules" ]; then
    echo "Установка зависимостей..."
    npm install
fi

# Запуск React dev сервера
# Исправление ошибки allowedHosts в webpack-dev-server
export DANGEROUSLY_DISABLE_HOST_CHECK=true
BROWSER=none npm start

