#!/bin/bash
# Скрипт для запуска теста v8 в Docker (из папки tests/)

cd "$(dirname "$0")/.." || exit 1

# Копируем скрипт теста в контейнер
docker cp tests/test_v8.py invoiceparser_app:/app/tests/test_v8.py

# Копируем новые промпты
docker cp prompts/header_v8.txt invoiceparser_app:/app/prompts/header_v8.txt
docker cp prompts/items_v8.txt invoiceparser_app:/app/prompts/items_v8.txt

# Запускаем батч-обработку
echo "🚀 Запуск теста v8..."
docker-compose exec -T app python /app/tests/test_v8.py
