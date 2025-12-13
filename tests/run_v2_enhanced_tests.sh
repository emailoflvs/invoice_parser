#!/bin/bash
# Скрипт для запуска тестов items_v2.txt с улучшенной подготовкой изображения

set -e

cd "$(dirname "$0")/.."

echo "Копирование тестовых скриптов в Docker контейнер..."
docker cp tests/test_v2_enhanced_preprocessing.py invoiceparser_app:/app/tests/test_v2_enhanced_preprocessing.py
docker cp tests/test_v2_binarized.py invoiceparser_app:/app/tests/test_v2_binarized.py

echo ""
echo "=========================================="
echo "ТЕСТ 1: Улучшенная подготовка (без бинаризации)"
echo "=========================================="
echo ""

docker-compose exec -T app python /app/tests/test_v2_enhanced_preprocessing.py 2>&1 | tee /tmp/v2_enhanced_test.log

echo ""
echo "=========================================="
echo "ТЕСТ 2: С бинаризацией"
echo "=========================================="
echo ""

docker-compose exec -T app python /app/tests/test_v2_binarized.py 2>&1 | tee /tmp/v2_binarized_test.log

echo ""
echo "=========================================="
echo "ТЕСТИРОВАНИЕ ЗАВЕРШЕНО"
echo "=========================================="
echo ""
echo "Результаты сохранены в:"
echo "  - /tmp/v2_enhanced_test.log"
echo "  - /tmp/v2_binarized_test.log"
echo ""
echo "JSON файлы сохранены в output/"






