#!/bin/bash
# Автоматический тест фронтенда из Docker (с авто-логином)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🐳 Автоматическое тестирование фронтенда из Docker"
echo "=================================================="

# Проверяем что контейнер запущен
CONTAINER_NAME="${APP_CONTAINER_NAME:-invoiceparser_app}"
if ! docker ps | grep -q "$CONTAINER_NAME"; then
    echo "❌ Контейнер $CONTAINER_NAME не запущен"
    exit 1
fi

echo "✅ Контейнер $CONTAINER_NAME запущен"

# Получаем токен автоматически (регистрируемся или логинимся)
echo ""
echo "🔐 Получение токена..."

# Пробуем зарегистрировать/залогиниться тестовым пользователем
TEST_USER="test_user_$(date +%s)"
TEST_PASS="test_pass_123"

# Сначала пробуем зарегистрироваться
REGISTER_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASS\"}" 2>/dev/null || echo "")

# Если регистрация не удалась, пробуем логиниться с теми же данными
if echo "$REGISTER_RESPONSE" | grep -q "already registered\|Username already"; then
    echo "   Пользователь уже существует, выполняю логин..."
    LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASS\"}" 2>/dev/null || echo "")
else
    # Пробуем логиниться после регистрации
    sleep 1
    LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8000/api/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$TEST_USER\",\"password\":\"$TEST_PASS\"}" 2>/dev/null || echo "")
fi

# Извлекаем токен
TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo "❌ Не удалось получить токен"
    echo "   Попробуйте вручную: curl -X POST http://localhost:8000/login -d 'username=USER&password=PASS'"
    exit 1
fi

echo "✅ Токен получен"
echo "$TOKEN" > /tmp/test_token.txt

# Запускаем тест
echo ""
echo "🧪 Запуск теста..."
echo ""

python3 -m pytest tests/test_frontend_data.py::test_frontend_data_parsing -v -s

echo ""
echo "✅ Тест завершен"

