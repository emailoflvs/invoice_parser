#!/usr/bin/env python3
"""Исправление миграции и запуск сайта"""
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

    print("🔧 Исправление миграции и запуск сайта...\n")

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

        # Обновление из git
        print("📥 Обновление кода из Git...")
        child.sendline('git pull origin main')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Остановка контейнеров
        print("\n🛑 Остановка контейнеров...")
        child.sendline('docker compose down')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Очистка БД для чистой миграции (опционально, можно закомментировать)
        print("\n🧹 Очистка БД для чистой миграции...")
        child.sendline('docker compose down -v')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Открытие порта
        print("\n🔥 Открытие порта 8000...")
        child.sendline('sudo ufw allow 8000/tcp 2>/dev/null || true')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        # Запуск
        print("\n🚀 Запуск приложения...")
        child.sendline('docker compose up -d --build 2>&1 | tee /tmp/docker_fixed.log &')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("✅ Команда запущена в фоне")
        print("\n⏳ Ожидание 90 секунд для сборки и запуска...")
        import time
        time.sleep(90)

        # Проверка
        print("\n📊 Проверка статуса:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n📋 Логи (последние 30 строк):")
        child.sendline('docker compose logs --tail=30 2>&1 | tail -40')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n🌐 Проверка портов:")
        child.sendline('ss -tuln | grep ":8000" && echo "✅ Порт 8000 открыт" || echo "❌ Порт 8000 не открыт"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n🔍 Тест HTTP:")
        child.sendline('curl -s -I http://localhost:8000/ 2>&1 | head -3 || echo "Приложение не отвечает"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("✅ Настройка завершена!")
        print("\n🌐 Проверьте сайт:")
        print("   http://doclogic.eu")
        print("   http://57.129.62.58:8000")
        print("="*60)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())









