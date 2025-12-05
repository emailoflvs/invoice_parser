#!/bin/bash

# Скрипт для запуска веб-интерфейса Invoice Parser

echo "🚀 Запуск Invoice Parser Web Interface..."
echo ""

# Проверка виртуального окружения
if [ ! -d "venv" ]; then
    echo "⚠️  Виртуальное окружение не найдено. Создаём..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 Установка зависимостей..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Проверка .env файла
if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден!"
    echo "📋 Скопируйте env.example в .env и заполните необходимые значения:"
    echo "   cp env.example .env"
    echo "   nano .env"
    exit 1
fi

# Запуск сервера
echo ""
echo "✅ Запуск веб-сервера..."
echo "🌐 Откройте браузер и перейдите по адресу: http://localhost:8000"
echo ""
echo "Для остановки нажмите Ctrl+C"
echo ""

python -m src.invoiceparser.app.main_web



