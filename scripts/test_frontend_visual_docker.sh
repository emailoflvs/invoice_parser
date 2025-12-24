#!/bin/bash
# Визуальный тест фронтенда из Docker (с Playwright на хосте)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🐳 Визуальное тестирование фронтенда (Docker)"
echo "=============================================="

# Проверяем что контейнер запущен
CONTAINER_NAME="${APP_CONTAINER_NAME:-invoiceparser_app}"
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Контейнер $CONTAINER_NAME не запущен"
    echo "   Запустите: docker-compose up -d"
    exit 1
fi

echo "✅ Контейнер $CONTAINER_NAME запущен"

# Проверяем что сервер доступен
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Сервер не доступен на localhost:8000"
    exit 1
fi

echo "✅ Сервер доступен на localhost:8000"

# Проверяем Playwright
if ! python3 -c "import playwright" 2>/dev/null; then
    echo "⚠️  Playwright не установлен"
    echo "   Установите: pip install playwright pytest-playwright && playwright install chromium"
    exit 1
fi

echo "✅ Playwright установлен"

# Получаем токен (используем скрипт из контейнера или создаем на хосте)
TOKEN_FILE="/tmp/test_token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "🔐 Получение токена..."

    # Копируем скрипт получения токена в контейнер и запускаем
    docker cp "$PROJECT_DIR/scripts/get_token_in_docker.py" "$CONTAINER_NAME:/app/get_token.py"
    TOKEN=$(docker exec "$CONTAINER_NAME" python3 /app/get_token.py 2>/dev/null || echo "")

    if [ -z "$TOKEN" ] || [ "$TOKEN" = "NO_TOKEN" ]; then
        echo "❌ Не удалось получить токен"
        exit 1
    fi

    echo "$TOKEN" > "$TOKEN_FILE"
    echo "✅ Токен сохранен"
fi

# Запускаем визуальный тест (Playwright на хосте, обращается к Docker через localhost:8000)
echo ""
echo "🧪 Запуск визуального теста..."
echo ""

python3 -m pytest tests/test_frontend_visual.py::test_frontend_visual_parsing -v -s

echo ""
echo "✅ Тест завершен"

