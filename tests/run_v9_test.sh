#!/bin/bash
# Скрипт для теста v9 с автоматическим повтором при квоте (из папки tests/)

cd "$(dirname "$0")/.." || exit 1

echo "🚀 Тестирование items_v9.txt на dnipromash.jpg"
echo ""

# Копируем файлы в контейнер
docker cp tests/test_v9.py invoiceparser_app:/app/tests/test_v9.py
docker cp prompts/items_v9.txt invoiceparser_app:/app/prompts/items_v9.txt

# Пытаемся запустить с повторами
MAX_RETRIES=3
RETRY_DELAY=60

for i in $(seq 1 $MAX_RETRIES); do
    echo "Попытка $i из $MAX_RETRIES..."

    if docker-compose exec -T app python /app/tests/test_v9.py 2>&1 | tee /tmp/v9_test_output.log; then
        echo ""
        echo "✅ Тест успешно завершен!"
        exit 0
    fi

    if grep -q "quota\|429" /tmp/v9_test_output.log; then
        if [ $i -lt $MAX_RETRIES ]; then
            echo ""
            echo "⏳ Квота исчерпана. Ожидание $RETRY_DELAY секунд перед повтором..."
            sleep $RETRY_DELAY
        else
            echo ""
            echo "❌ Квота API исчерпана. Попробуйте позже (через ~24 часа)."
            exit 1
        fi
    else
        echo ""
        echo "❌ Ошибка при выполнении теста"
        exit 1
    fi
done
