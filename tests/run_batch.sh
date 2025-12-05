#!/bin/bash
# Скрипт для запуска батч-обработки в Docker (из папки tests/)

cd "$(dirname "$0")/.." || exit 1

# Проверяем, запущен ли контейнер
if ! docker ps | grep -q invoiceparser_app; then
    echo "⚠️  Контейнер invoiceparser_app не запущен. Запускаю..."
    docker-compose up -d app
    sleep 3
fi

# Копируем скрипт в контейнер (если его там нет)
docker cp tests/batch_process.py invoiceparser_app:/app/tests/batch_process.py

# Запускаем батч-обработку
echo "🚀 Запуск батч-обработки..."
docker-compose exec -T app python /app/tests/batch_process.py
