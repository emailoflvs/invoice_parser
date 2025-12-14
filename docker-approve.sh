#!/bin/bash
# Скрипт для подтверждения данных и экспорта из Docker контейнера

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Проверяем аргументы
if [ $# -lt 1 ]; then
    echo "Usage: $0 <path_to_json> [original_filename]"
    echo "Example: $0 output/invoice_gemini_14120108_0errors.json invoice.jpg"
    exit 1
fi

JSON_PATH="$1"
ORIGINAL_FILENAME="${2:-}"

# Проверяем, что файл существует
if [ ! -f "$JSON_PATH" ]; then
    echo "Error: File not found: $JSON_PATH"
    exit 1
fi

# Запускаем approve в Docker
echo "✅ Approving data from: $JSON_PATH"
if [ -n "$ORIGINAL_FILENAME" ]; then
    docker-compose exec app python -m invoiceparser.app.main_cli approve --json "/app/$JSON_PATH" --original-filename "$ORIGINAL_FILENAME" 2>&1
else
    docker-compose exec app python -m invoiceparser.app.main_cli approve --json "/app/$JSON_PATH" 2>&1
fi

echo ""
echo "✅ Export completed"

