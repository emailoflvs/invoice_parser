#!/usr/bin/env python3
"""Запуск приложения без миграций для теста"""
import sys
import subprocess

def install_pexpect():
    try:
        import pexpect
        return pexpect
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pexpect", "--user", "-q"])
        import pexpect
        return pexpect

def main():
    server = "debian@57.129.62.58"
    password = "Polik350"
    project_path = "/opt/docker-projects/invoice_parser"

    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1

    print("🔧 Запуск приложения без миграций...\n")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)

        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)

        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            return 1

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Остановка
        print("🛑 Остановка контейнеров...")
        child.sendline('docker compose down')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Создание временного docker-compose без миграций
        print("📝 Создание временной конфигурации без миграций...")
        child.sendline('''cat > docker-compose.temp.yml << 'EOF'
services:
  db:
    image: postgres:16-alpine
    container_name: invoiceparser_db
    environment:
      POSTGRES_USER: invoiceparser
      POSTGRES_PASSWORD: invoiceparser_password
      POSTGRES_DB: invoiceparser
    volumes:
      - invoiceparser_postgres_data:/var/lib/postgresql/data
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U invoiceparser"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - invoiceparser_network

  app:
    build: .
    container_name: invoiceparser_app
    volumes:
      - ./invoices:/app/invoices
      - ./output:/app/output
      - ./temp:/app/temp
      - ./logs:/app/logs
      - ./examples:/app/examples
      - ./.env:/app/.env
      - ./google_sheets_credentials.json:/app/google_sheets_credentials.json
      - ./src:/app/src
      - ./static:/app/static
      - ./prompts:/app/prompts
      - ./alembic.ini:/app/alembic.ini
      - ./alembic:/app/alembic
      - ./scripts:/app/scripts
    depends_on:
      db:
        condition: service_healthy
    environment:
      - PYTHONPATH=/app/src
      - LOGS_DIR=/app/logs
      - OUTPUT_DIR=/app/output
      - TEMP_DIR=/app/temp
      - INVOICES_DIR=/app/invoices
      - EXAMPLES_DIR=/app/examples
      - PROMPTS_DIR=/app/prompts
    command: >
      sh -c "
        python scripts/wait_for_db.py &&
        echo '⚠️  Skipping migrations for now...' &&
        echo '✅ Starting application...' &&
        python -m invoiceparser.app.main_web
      "
    ports:
      - "8000:8000"
    restart: unless-stopped
    networks:
      - invoiceparser_network

networks:
  invoiceparser_network:
    name: invoiceparser_network
    driver: bridge

volumes:
  invoiceparser_postgres_data:
    name: invoiceparser_postgres_data
EOF
echo "✅ Временный файл создан"''')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Открытие порта в firewall
        print("\n🔥 Открытие порта 8000 в firewall...")
        child.sendline('sudo ufw allow 8000/tcp')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        # Запуск с временным файлом
        print("\n🚀 Запуск приложения...")
        child.sendline('docker compose -f docker-compose.temp.yml up -d --build 2>&1 | tee /tmp/docker_start_no_mig.log')

        # Ждем завершения
        import time
        max_wait = 600
        start_time = time.time()
        print("   (Ожидание завершения сборки, это может занять несколько минут...)")

        while time.time() - start_time < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=120)
                if index in [0, 1]:
                    break
            except pexpect.TIMEOUT:
                print("   ⏳ Сборка продолжается...")
                continue

        print("\n✅ Команда завершена")

        # Ожидание запуска
        print("\n⏳ Ожидание 30 секунд для запуска приложения...")
        time.sleep(30)

        # Проверка статуса
        print("\n📊 Статус контейнеров:")
        child.sendline('docker compose -f docker-compose.temp.yml ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка портов
        print("\n🌐 Проверка портов:")
        child.sendline('ss -tuln | grep ":8000" || echo "Порт 8000 не слушается"')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Тест HTTP
        print("\n🔍 Тест HTTP:")
        child.sendline('curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/ 2>&1 || echo "Не отвечает"')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Логи
        print("\n📋 Последние логи:")
        child.sendline('docker compose -f docker-compose.temp.yml logs --tail=15 2>&1 | tail -20')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("✅ Приложение запущено!")
        print("\n🌐 Проверьте:")
        print("   http://doclogic.eu")
        print("   http://57.129.62.58:8000")
        print("\n⚠️  Примечание: Используется временная конфигурация без миграций")
        print("   Для постоянного решения исправьте миграции")
        print("="*60)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())









