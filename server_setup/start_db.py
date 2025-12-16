#!/usr/bin/env python3
"""Запуск БД и приложения"""
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

    print("🗄️  Запуск БД и приложения...\n")

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

        print("\n=== ЗАПУСК БД И ПРИЛОЖЕНИЯ ===")
        child.sendline('docker compose up -d --build')

        max_wait = 300
        start = time.time()
        while time.time() - start < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=120)
                if index in [0, 1]:
                    break
            except:
                continue

        print("\n⏳ Ожидание 90 секунд для запуска...")
        time.sleep(90)

        print("\n=== СТАТУС ===")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ПРОВЕРКА БД ===")
        child.sendline('docker compose logs db --tail=10')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ПРОВЕРКА ПРИЛОЖЕНИЯ ===")
        child.sendline('docker compose logs app --tail=20')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ТЕСТ HTTP ===")
        child.sendline('curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8000/')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        print("\n✅ Готово!")
        print("🌐 https://doclogic.eu")
        print("🌐 http://57.129.62.58:8000")

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

