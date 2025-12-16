#!/usr/bin/env python3
"""Проверка применения исправлений на сервере"""

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
    print("🔍 Проверяю применение исправлений...")

    # 1. Проверяем версию файла gemini_client.py на сервере
    print("\n1️⃣  Проверяю gemini_client.py на сервере...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep -A 2 'Prompt file not found' src/invoiceparser/services/gemini_client.py")
    print(output)

    if "ERROR_E006" in output:
        print("✅ Исправление применено в исходном файле!")
    else:
        print("⚠️  Исправление не найдено в исходном файле")

    # 2. Проверяем версию файла в контейнере
    print("\n2️⃣  Проверяю gemini_client.py в контейнере...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app grep -A 2 'Prompt file not found' /app/src/invoiceparser/services/gemini_client.py")
    print(output)

    if "ERROR_E006" in output:
        print("✅ Исправление применено в контейнере!")
    else:
        print("⚠️  Исправление не найдено в контейнере")

    # 3. Проверяем web_api.py
    print("\n3️⃣  Проверяю web_api.py (обработка E006)...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app grep 'E006' /app/src/invoiceparser/adapters/web_api.py")
    print(output)

    if "E006" in output:
        print("✅ Обработка E006 добавлена в web_api.py!")

    # 4. Проверяем script.js
    print("\n4️⃣  Проверяю script.js (обработка E006)...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app grep 'E006' /app/static/script.js")
    print(output)

    if "E006" in output:
        print("✅ Обработка E006 добавлена в script.js!")

    # 5. Проверяем логи приложения
    print("\n5️⃣  Проверяю логи приложения (последние 10 строк)...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=10 app")
    print(output)

    # 6. Проверяем статус контейнеров
    print("\n6️⃣  Статус контейнеров:")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose ps")
    print(output)

    print("\n✅ Проверка завершена!")

if __name__ == "__main__":
    main()

