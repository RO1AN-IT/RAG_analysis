#!/bin/bash

# Скрипт для остановки процессов, использующих указанный порт

PORT=$1

if [ -z "$PORT" ]; then
    echo "Использование: $0 <номер_порта>"
    echo ""
    echo "Примеры:"
    echo "  $0 3000  # Остановить React dev server"
    echo "  $0 8000  # Остановить Django server"
    exit 1
fi

echo "Поиск процессов, использующих порт $PORT..."

# Найти PID процесса, использующего порт
PID=$(lsof -ti :$PORT)

if [ -z "$PID" ]; then
    echo "✅ Порт $PORT свободен."
    exit 0
else
    echo "Найден(ы) процесс(ы) с PID: $PID на порту $PORT."
    echo "Остановка процесса(ов)..."
    kill $PID
    
    # Проверить, остановлен ли процесс
    sleep 1
    if lsof -ti :$PORT > /dev/null 2>&1; then
        echo "Процесс не остановлен, принудительная остановка (kill -9)..."
        kill -9 $PID 2>/dev/null
        sleep 1
        if lsof -ti :$PORT > /dev/null 2>&1; then
            echo "❌ Не удалось остановить процесс на порту $PORT."
            exit 1
        else
            echo "✅ Процесс на порту $PORT успешно остановлен (kill -9)."
        fi
    else
        echo "✅ Процесс на порту $PORT успешно остановлен."
    fi
fi

