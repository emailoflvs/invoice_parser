#!/usr/bin/env python3
"""Обновление фронтенда на сервере"""

import pexpect

SERVER = "debian@57.129.62.58"
PASSWORD = "Polik350"
PROJECT_DIR = "/opt/docker-projects/invoice_parser"

def run_ssh_command(command, timeout=60):
    """Выполнение SSH команды"""
    try:
        child = pexpect.spawn(f'ssh {SERVER} "{command}"', encoding='utf-8', timeout=timeout)
        index = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(PASSWORD)
            child.expect(pexpect.EOF, timeout=timeout)
        output = str(child.before) + (str(child.after) if hasattr(child, 'after') and child.after else '')
        return output.strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    print("🚀 Обновляю фронтенд на сервере...")

    # 1. Обновляем код из репозитория
    print("\n1️⃣  Обновляю код из репозитория...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && git pull")
    print(output)

    # 2. Перезапускаем контейнер app
    print("\n2️⃣  Перезапускаю контейнер app...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose restart app", timeout=60)
    print(output)

    # 3. Проверяем статус
    print("\n3️⃣  Проверяю статус контейнеров...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose ps")
    print(output)

    # 4. Проверяем логи (последние 10 строк)
    print("\n4️⃣  Проверяю логи приложения...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=10 app")
    print(output)

    print("\n✅ Фронтенд обновлен на сервере!")

if __name__ == "__main__":
    main()









