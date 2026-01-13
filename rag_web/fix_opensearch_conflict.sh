#!/bin/bash
# Скрипт для решения конфликта имени контейнера OpenSearch

echo "=========================================="
echo "Решение конфликта контейнера OpenSearch"
echo "=========================================="

# Проверить существующие контейнеры
echo ""
echo "Проверка существующих контейнеров..."
docker ps -a | grep -E "opensearch|CONTAINER"

# Остановить и удалить старые контейнеры
echo ""
echo "Остановка старых контейнеров..."
docker stop opensearch opensearch-dashboards 2>/dev/null || true

echo "Удаление старых контейнеров..."
docker rm opensearch opensearch-dashboards 2>/dev/null || true

# Проверить, что контейнеры удалены
echo ""
echo "Проверка, что контейнеры удалены..."
if docker ps -a | grep -q opensearch; then
    echo "⚠️  Внимание: некоторые контейнеры все еще существуют"
    docker ps -a | grep opensearch
    echo ""
    read -p "Удалить принудительно? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker rm -f opensearch opensearch-dashboards 2>/dev/null || true
    fi
else
    echo "✓ Старые контейнеры удалены"
fi

# Запустить новые контейнеры
echo ""
echo "Запуск новых контейнеров..."
cd "$(dirname "$0")"
docker compose -f docker-compose.opensearch.yml up -d

# Проверить статус
echo ""
echo "Проверка статуса..."
sleep 3
docker compose -f docker-compose.opensearch.yml ps

# Проверить доступность
echo ""
echo "Проверка доступности OpenSearch..."
sleep 5
if curl -s http://localhost:9200 > /dev/null; then
    echo "✓ OpenSearch доступен!"
    curl -s http://localhost:9200 | head -5
else
    echo "⚠️  OpenSearch еще не готов, проверьте логи:"
    echo "   docker compose -f docker-compose.opensearch.yml logs"
fi

echo ""
echo "=========================================="
echo "Готово!"
echo "=========================================="







