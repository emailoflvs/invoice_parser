#!/bin/bash
# Скрипт для копирования проекта на сервер
# Использование: ./deploy_to_server.sh

set -e

SERVER="debian@57.129.62.58"
SERVER_PATH="/opt/docker-projects/invoice_parser"
LOCAL_PATH="/home/lvs/Desktop/AI/servers/invoice_parser"

echo "🚀 Развертывание проекта на сервер..."
echo "Сервер: $SERVER"
echo "Путь на сервере: $SERVER_PATH"
echo ""

# Проверка подключения
echo "🔍 Проверка подключения к серверу..."
if ! ssh -o ConnectTimeout=5 "$SERVER" "echo 'Connected'" 2>/dev/null; then
    echo "❌ Не удалось подключиться к серверу"
    echo "Попробуйте подключиться вручную: ssh $SERVER"
    exit 1
fi

# Создание директории на сервере
echo "📁 Создание директории на сервере..."
ssh "$SERVER" "sudo mkdir -p $SERVER_PATH && sudo chown -R debian:debian $SERVER_PATH"

# Копирование файлов
echo "📦 Копирование файлов на сервер..."
rsync -avz --progress \
    --exclude 'venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.git' \
    --exclude '*.log' \
    --exclude 'temp/' \
    --exclude 'output/arch/' \
    --exclude 'output/temp/' \
    --exclude 'output/prompt_tests/' \
    --exclude 'output/v6/' \
    --exclude 'node_modules' \
    --exclude '.env' \
    "$LOCAL_PATH/" \
    "$SERVER:$SERVER_PATH/"

echo ""
echo "✅ Файлы скопированы на сервер"
echo ""
echo "📋 Следующие шаги на сервере:"
echo "1. Подключитесь: ssh $SERVER"
echo "2. Перейдите в директорию: cd $SERVER_PATH"
echo "3. Создайте .env файл (если его нет): cp .env.example .env && nano .env"
echo "4. Запустите проект: docker compose up -d --build"
echo "5. Проверьте логи: docker compose logs -f"









