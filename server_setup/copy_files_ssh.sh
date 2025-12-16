#!/bin/bash
# Скрипт для копирования файлов на сервер через SSH
# Использование: ./copy_files_ssh.sh [файл1] [файл2] ...

SERVER="debian@57.129.62.58"
SERVER_PATH="/opt/docker-projects/invoice_parser"
LOCAL_PATH="/home/lvs/Desktop/AI/servers/invoice_parser"

echo "📤 Копирование файлов на сервер..."

# Если переданы аргументы, копируем их
if [ $# -gt 0 ]; then
    for file in "$@"; do
        if [ -f "$LOCAL_PATH/$file" ]; then
            echo "  Копирую $file..."
            scp "$LOCAL_PATH/$file" "$SERVER:$SERVER_PATH/$file"
        else
            echo "  ⚠️  Файл $file не найден"
        fi
    done
else
    # Копируем стандартные файлы
    echo "Копирую стандартные файлы..."

    # .env файл
    if [ -f "$LOCAL_PATH/.env" ]; then
        echo "  Копирую .env..."
        scp "$LOCAL_PATH/.env" "$SERVER:$SERVER_PATH/.env"
    fi

    # Google Sheets credentials
    if [ -f "$LOCAL_PATH/google_sheets_credentials.json" ]; then
        echo "  Копирую google_sheets_credentials.json..."
        scp "$LOCAL_PATH/google_sheets_credentials.json" "$SERVER:$SERVER_PATH/google_sheets_credentials.json"
    fi
fi

echo "✅ Готово!"

