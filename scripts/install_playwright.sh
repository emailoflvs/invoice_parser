#!/bin/bash
# Установка Playwright для визуального тестирования

echo "📦 Установка Playwright..."
pip install playwright pytest-playwright
echo "🌐 Установка браузера Chromium..."
playwright install chromium
echo "✅ Playwright установлен и готов к использованию"

