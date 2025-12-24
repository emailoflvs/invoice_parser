#!/bin/bash
# Тест фронтенда из Docker контейнера

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🐳 Тестирование фронтенда из Docker"
echo "===================================="

# Проверяем что контейнер запущен
CONTAINER_NAME="${APP_CONTAINER_NAME:-invoiceparser_app}"
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Контейнер $CONTAINER_NAME не запущен"
    echo "   Запустите: docker-compose up -d"
    exit 1
fi

echo "✅ Контейнер $CONTAINER_NAME запущен"

# Копируем тест в контейнер
echo "📋 Копирую тестовый файл в контейнер..."
docker exec "$CONTAINER_NAME" mkdir -p /app/tests
docker cp "$PROJECT_DIR/tests/test_frontend_data.py" "$CONTAINER_NAME:/app/tests/test_frontend_data.py"
docker cp "$PROJECT_DIR/tests/conftest.py" "$CONTAINER_NAME:/app/tests/conftest.py" 2>/dev/null || true

# Копируем скрипт получения токена
docker cp "$PROJECT_DIR/scripts/get_token_in_docker.py" "$CONTAINER_NAME:/app/get_token.py"

# Получаем токен внутри контейнера
echo "🔐 Получение токена внутри контейнера..."
TOKEN=$(docker exec "$CONTAINER_NAME" python3 /app/get_token.py 2>/dev/null || echo "")

if [ -z "$TOKEN" ] || [ "$TOKEN" = "NO_TOKEN" ]; then
    echo "❌ Не удалось получить токен"
    exit 1
fi

echo "✅ Токен получен"

# Сохраняем токен в контейнере
echo "$TOKEN" | docker exec -i "$CONTAINER_NAME" tee /tmp/test_token.txt > /dev/null

# Запускаем тест внутри контейнера
echo ""
echo "🧪 Запуск теста внутри контейнера..."
echo ""

docker exec -w /app "$CONTAINER_NAME" python3 -m pytest tests/test_frontend_data.py::test_frontend_data_parsing -v -s

echo ""
echo "✅ Тест завершен"
