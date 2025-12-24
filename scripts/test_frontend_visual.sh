#!/bin/bash
# Скрипт для визуального тестирования фронтенда
# Парсит документ через API, открывает в браузере, делает скриншот и анализирует

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Запуск визуального теста фронтенда"
echo "======================================"

# Проверяем что сервер запущен
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Сервер не запущен на localhost:8000"
    echo "   Запустите: python -m uvicorn src.invoiceparser.adapters.web_api:app --reload --host 0.0.0.0 --port 8000"
    exit 1
fi

# Проверяем токен
TOKEN_FILE="/tmp/test_token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
    echo "⚠️  Токен не найден. Выполняю логин..."

    # Запрашиваем логин
    read -p "Username: " USERNAME
    read -sp "Password: " PASSWORD
    echo

    # Логинимся
    RESPONSE=$(curl -s -X POST "http://localhost:8000/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "username=$USERNAME&password=$PASSWORD")

    TOKEN=$(echo "$RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

    if [ -z "$TOKEN" ]; then
        echo "❌ Ошибка логина"
        exit 1
    fi

    echo "$TOKEN" > "$TOKEN_FILE"
    echo "✅ Токен сохранен в $TOKEN_FILE"
fi

# Устанавливаем Playwright браузеры (если еще не установлены)
if ! python3 -c "import playwright" 2>/dev/null; then
    echo "📦 Установка Playwright..."
    pip install playwright pytest-playwright
    playwright install chromium
fi

# Запускаем тест
echo ""
echo "🧪 Запуск теста..."
pytest tests/test_frontend_visual.py -v -s

echo ""
echo "✅ Тест завершен"
echo "📁 Результаты сохранены во временной директории (путь в выводе выше)"

