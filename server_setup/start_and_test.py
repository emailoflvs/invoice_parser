#!/usr/bin/env python3
"""Запуск сервера и тестирование"""
import sys
import subprocess
import time

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

    print("🚀 Запуск сервера...")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)

        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            return 1

        print("✅ Подключен к серверу")

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Остановка существующих контейнеров
        print("\n🛑 Остановка существующих контейнеров (если есть)...")
        child.sendline('docker compose down 2>/dev/null || true')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Проверка файлов
        print("\n📋 Проверка необходимых файлов...")
        child.sendline('ls -lh .env docker-compose.yml Dockerfile 2>/dev/null | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Запуск в фоне
        print("\n🔨 Запуск Docker Compose (это может занять несколько минут)...")
        print("   Сборка образов и запуск контейнеров...")
        child.sendline('docker compose up -d --build > /tmp/docker_start.log 2>&1 &')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("✅ Команда запущена в фоне")
        print("\n⏳ Ожидание запуска контейнеров (30 секунд)...")

        # Ждем немного
        time.sleep(30)

        # Проверка статуса
        print("\n📊 Проверка статуса контейнеров...")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка логов
        print("\n📋 Последние логи (20 строк)...")
        child.sendline('docker compose logs --tail=20 2>&1 | head -30')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка портов
        print("\n🌐 Проверка открытых портов...")
        child.sendline('docker compose ps | grep -E "PORTS|0.0.0.0" || ss -tuln | grep -E "8000|5433" || netstat -tuln | grep -E "8000|5433"')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка доступности приложения
        print("\n🔍 Проверка доступности приложения...")
        child.sendline('curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/health 2>/dev/null || curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/ 2>/dev/null || echo "Приложение еще запускается..."')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Информация о контейнерах
        print("\n📦 Информация о контейнерах:")
        child.sendline('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("✅ Сервер запущен!")
        print("\n📝 Полезные команды:")
        print(f"   ssh {server}")
        print(f"   cd {project_path}")
        print("   docker compose ps          # Статус")
        print("   docker compose logs -f     # Логи")
        print("   docker compose restart     # Перезапуск")
        print("\n🌐 Доступ к приложению:")
        print(f"   http://57.129.62.58:8000")
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

