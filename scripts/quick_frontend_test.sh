#!/bin/bash
# Быстрый тест фронтенда (без браузера, только данные)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "🧪 Быстрый тест данных фронтенда"
echo "================================"

# Проверяем сервер
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "❌ Сервер не запущен"
    exit 1
fi

# Проверяем токен
if [ ! -f "/tmp/test_token.txt" ]; then
    echo "⚠️  Токен не найден. Запустите:"
    echo "   curl -X POST 'http://localhost:8000/login' -d 'username=USER&password=PASS' | python3 -c \"import sys, json; print(json.load(sys.stdin)['access_token'])\" > /tmp/test_token.txt"
    exit 1
fi

# Запускаем тест
pytest tests/test_frontend_data.py -v -s

