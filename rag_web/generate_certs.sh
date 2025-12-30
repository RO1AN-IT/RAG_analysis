#!/bin/bash
# Скрипт для генерации SSL сертификатов для OpenSearch
# Использует openssl напрямую (не требует запуска Docker контейнера)

set -e

echo "=========================================="
echo "Генерация SSL сертификатов для OpenSearch"
echo "=========================================="
echo ""

# Проверяем наличие openssl
if ! command -v openssl &> /dev/null; then
    echo "❌ openssl не установлен. Установите:"
    echo "   Ubuntu/Debian: sudo apt-get install openssl"
    echo "   CentOS/RHEL: sudo yum install openssl"
    exit 1
fi

CERT_DIR="opensearch-certs"

# Создаем директорию для сертификатов
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

echo "1. Создание корневого CA..."
openssl genrsa -out root-ca-key.pem 2048
openssl req -new -x509 -sha256 -key root-ca-key.pem -subj '/C=DE/ST=Test/L=Test/O=Test/CN=root' -out root-ca.pem -days 730

echo "2. Создание ключа для HTTP сертификата..."
openssl genrsa -out http-key.pem 2048

echo "3. Создание запроса на сертификат..."
openssl req -new -key http-key.pem -subj '/C=DE/ST=Test/L=Test/O=Test/CN=admin' -out http.csr

echo "4. Подписание сертификата..."
openssl x509 -req -in http.csr -CA root-ca.pem -CAkey root-ca-key.pem -CAcreateserial -out http.pem -days 730 -sha256

echo "5. Очистка временных файлов..."
rm -f http.csr root-ca-key.pem root-ca.srl

echo "6. Установка прав доступа..."
chmod 644 *.pem 2>/dev/null || true
chmod 600 http-key.pem 2>/dev/null || true

echo ""
echo "=========================================="
echo "✓ Сертификаты успешно сгенерированы!"
echo "=========================================="
echo ""
echo "Файлы в директории $CERT_DIR:"
ls -lh *.pem 2>/dev/null || ls -lh
echo ""
echo "Следующие шаги:"
echo "1. Убедитесь, что в docker-compose.yml указан правильный путь к сертификатам"
echo "2. Запустите: docker compose up -d"
echo ""
