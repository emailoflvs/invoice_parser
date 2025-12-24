#!/usr/bin/env python3
"""Проверка содержимого gemini_client.py"""

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
    print("🔍 Проверяю содержимое gemini_client.py...")

    # Проверяем строку с ошибкой
    print("\n1️⃣  Ищу строку с обработкой ошибки файла промпта...")
    output = run_ssh_command(
        f"cd {PROJECT_DIR} && docker compose exec -T app grep -n 'exists' /app/src/invoiceparser/services/gemini_client.py | head -5"
    )
    print(output)

    # Проверяем конкретную строку с ошибкой
    print("\n2️⃣  Проверяю строки вокруг обработки ошибки...")
    output = run_ssh_command(
        f"cd {PROJECT_DIR} && docker compose exec -T app sed -n '260,265p' /app/src/invoiceparser/services/gemini_client.py"
    )
    print(output)

    # Проверяем наличие ERROR_E006
    print("\n3️⃣  Проверяю наличие ERROR_E006...")
    output = run_ssh_command(
        f"cd {PROJECT_DIR} && docker compose exec -T app grep 'ERROR_E006' /app/src/invoiceparser/services/gemini_client.py"
    )
    print(output)

    if "ERROR_E006" in output:
        print("✅ Исправление найдено!")
    else:
        print("❌ Исправление не найдено - нужно пересобрать контейнер")

if __name__ == "__main__":
    main()










