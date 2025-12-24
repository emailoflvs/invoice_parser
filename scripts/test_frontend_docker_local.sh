#!/bin/bash
# Тест фронтенда снаружи докера (обращается к localhost:8000)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🐳 Тестирование фронтенда (Docker на localhost:8000)"
echo "===================================================="

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

# Проверяем токен
TOKEN_FILE="/tmp/test_token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "⚠️  Токен не найден. Выполняю логин..."
    
    read -p "Username: " USERNAME
    read -sp "Password: " PASSWORD
    echo
    
    RESPONSE=$(curl -s -X POST "http://localhost:8000/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=$USERNAME&password=$PASSWORD")
    
    TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)
    
    if [ -z "$TOKEN" ]; then
        echo "❌ Ошибка логина"
        exit 1
    fi
    
    echo "$TOKEN" > "$TOKEN_FILE"
    echo "✅ Токен сохранен"
fi

# Запускаем тест локально (но обращается к докеру)
echo ""
echo "🧪 Запуск теста..."
echo ""

pytest tests/test_frontend_data.py -v -s

echo ""
echo "✅ Тест завершен"

