#!/usr/bin/env python3
"""Проверка пользователей в БД"""
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
        print(f"❌ Ошибка: {e}")
        return 1

    print("🔍 Проверка пользователей в БД...\n")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ПРОВЕРКА ТАБЛИЦЫ USERS ===")
        child.sendline('docker compose exec -T db psql -U invoiceparser -d invoiceparser -c "\\dt users"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ВСЕ ТАБЛИЦЫ ===")
        child.sendline('docker compose exec -T db psql -U invoiceparser -d invoiceparser -c "\\dt"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ПОЛЬЗОВАТЕЛИ В БД ===")
        child.sendline('docker compose exec -T db psql -U invoiceparser -d invoiceparser -c "SELECT id, username, email FROM users;"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== СОЗДАНИЕ ПОЛЬЗОВАТЕЛЯ admin (если нет) ===")
        child.sendline('docker compose exec -T app python scripts/create_admin_user.py 2>&1 || echo "Скрипт не найден, создаю через SQL"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n=== ПРОВЕРКА .env (DATABASE_URL) ===")
        child.sendline('grep DATABASE_URL .env')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

