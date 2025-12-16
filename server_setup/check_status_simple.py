#!/usr/bin/env python3
"""Простая проверка статуса сервера"""
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

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile_read = None  # Отключаем вывод для избежания проблем с кодировкой

        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)

        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            return 1

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка процесса сборки
        print("🔍 Проверка процесса сборки...")
        child.sendline('ps aux | grep "docker compose" | grep -v grep || echo "Сборка завершена"')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка логов сборки
        print("\n📋 Логи сборки (последние 30 строк):")
        child.sendline('tail -30 /tmp/docker_start.log 2>/dev/null || echo "Логи не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Статус контейнеров
        print("\n📊 Статус контейнеров:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Все контейнеры
        print("\n📦 Все Docker контейнеры:")
        child.sendline('docker ps -a')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Логи приложения
        print("\n📋 Логи приложения (последние 20 строк):")
        child.sendline('docker compose logs --tail=20 2>&1 | tail -30')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка портов
        print("\n🌐 Проверка портов:")
        child.sendline('ss -tuln 2>/dev/null | grep -E "8000|5433" || echo "Порты не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

