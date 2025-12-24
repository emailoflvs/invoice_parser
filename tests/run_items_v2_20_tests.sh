#!/bin/bash
# Скрипт для запуска автоматического тестирования items_v2.txt с 20 различными настройками обработки изображений

cd "$(dirname "$0")/.." || exit 1

echo "Запуск автоматического тестирования items_v2.txt с 20 конфигурациями..."
echo ""

python3 tests/test_items_v2_20_configs.py

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "✅ Все тесты завершены успешно!"
else
    echo ""
    echo "❌ Произошла ошибка при выполнении тестов (код выхода: $exit_code)"
fi

exit $exit_code















