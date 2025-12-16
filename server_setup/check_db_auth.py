#!/usr/bin/env python3
"""Проверка БД и аутентификации"""
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

    print("🔍 Проверка БД и аутентификации...\n")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("1️⃣  ПРОВЕРКА .env НА СЕРВЕРЕ")
        print("="*60)
        child.sendline('grep -E "DB_|DATABASE_" .env | head -10')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("2️⃣  СТАТУС БД")
        print("="*60)
        child.sendline('docker compose ps db')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("3️⃣  ПОДКЛЮЧЕНИЕ К БД")
        print("="*60)
        child.sendline('docker compose exec -T db psql -U invoiceparser -d invoiceparser -c "SELECT version();"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("4️⃣  ПРОВЕРКА ТАБЛИЦЫ USERS")
        print("="*60)
        child.sendline('docker compose exec -T db psql -U invoiceparser -d invoiceparser -c "SELECT table_name FROM information_schema.tables WHERE table_schema = \'public\' AND table_name = \'users\';"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("5️⃣  ПРОВЕРКА ПОЛЬЗОВАТЕЛЕЙ В БД")
        print("="*60)
        child.sendline('docker compose exec -T db psql -U invoiceparser -d invoiceparser -c "SELECT id, username, email, created_at FROM users LIMIT 5;"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("6️⃣  ПРОВЕРКА ПОДКЛЮЧЕНИЯ ИЗ ПРИЛОЖЕНИЯ")
        print("="*60)
        child.sendline('docker compose logs app --tail=30 | grep -iE "database|connection|error|user|auth" | tail -15')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("7️⃣  СОЗДАНИЕ ТЕСТОВОГО ПОЛЬЗОВАТЕЛЯ (если нет)")
        print("="*60)
        child.sendline('docker compose exec -T app python -c "from src.invoiceparser.database import get_session; from src.invoiceparser.models.user import User; from passlib.context import CryptContext; import sys; pwd_context = CryptContext(schemes=[\"bcrypt\"], deprecated=\"auto\"); session = next(get_session()); user = session.query(User).filter(User.username == \"admin\").first(); print(f\"User exists: {user is not None}\"); print(f\"User: {user.username if user else None}\"); sys.exit(0)" 2>&1')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

