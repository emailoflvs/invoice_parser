#!/bin/bash
# Скрипт для запуска парсинга из Docker контейнера

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Проверяем аргументы
if [ $# -lt 1 ]; then
    echo "Usage: $0 <path_to_document> [output_dir]"
    echo "Example: $0 invoices/invoice.jpg"
    exit 1
fi

DOCUMENT_PATH="$1"
OUTPUT_DIR="${2:-output}"

# Проверяем, что файл существует
if [ ! -f "$DOCUMENT_PATH" ]; then
    echo "Error: File not found: $DOCUMENT_PATH"
    exit 1
fi

# Запускаем парсинг в Docker
echo "🔍 Parsing document: $DOCUMENT_PATH"
docker-compose exec app python -m invoiceparser.app.main_cli parse --path "/app/$DOCUMENT_PATH" 2>&1

echo ""
echo "✅ Parsing completed. Check output directory: $OUTPUT_DIR"

