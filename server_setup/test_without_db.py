#!/usr/bin/env python3
"""Тестирование без БД в docker-compose"""
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
        print(f"❌ Ошибка: {e}")
        return 1

    print("🧪 Тестирование без БД в docker-compose...\n")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ОБНОВЛЕНИЕ КОДА ===")
        child.sendline('git pull origin main')
        child.expect([r'\$ ', r'# '], timeout=30)

        print("\n=== ОСТАНОВКА ===")
        child.sendline('docker compose down')
        child.expect([r'\$ ', r'# '], timeout=30)

        print("\n=== ЗАПУСК (только app) ===")
        child.sendline('docker compose up -d --build app')

        max_wait = 300
        start = time.time()
        while time.time() - start < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=120)
                if index in [0, 1]:
                    break
            except:
                continue

        print("\n⏳ Ожидание 60 секунд...")
        time.sleep(60)

        print("\n=== СТАТУС ===")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ЛОГИ (последние 40 строк) ===")
        child.sendline('docker compose logs app --tail=40')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ПОРТЫ ===")
        child.sendline('ss -tuln | grep 8000 && echo "✅ Порт 8000 открыт" || echo "❌ Порт 8000 не открыт"')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

