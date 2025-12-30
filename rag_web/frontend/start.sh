#!/bin/bash
# Скрипт для запуска React frontend с правильными настройками окружения

cd "$(dirname "$0")"

# Устанавливаем временную директорию, если проблема с внешним диском
export TMPDIR=/tmp

# Отключаем автоматическое открытие браузера
export BROWSER=none

# Запускаем React development server
npm start

