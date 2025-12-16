#!/usr/bin/env python3
"""Тестирование работы приложения после исправления"""

import pexpect
import requests
import time

SERVER = "debian@57.129.62.58"
PASSWORD = "Polik350"
PROJECT_DIR = "/opt/docker-projects/invoice_parser"
DOMAIN = "https://doclogic.eu"

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
    print("🧪 Тестирование работы приложения...")

    # 1. Проверяем статус контейнеров
    print("\n1️⃣  Проверяю статус контейнеров...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose ps")
    print(output)

    # 2. Проверяем логи (последние 10 строк)
    print("\n2️⃣  Проверяю логи приложения...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=10 app")
    print(output)

    # 3. Проверяем доступность домена
    print("\n3️⃣  Проверяю доступность домена...")
    try:
        response = requests.get(f"{DOMAIN}/", timeout=10, verify=False)
        print(f"✅ Домен доступен: {response.status_code}")
    except Exception as e:
        print(f"⚠️  Ошибка при проверке домена: {e}")

    # 4. Проверяем, что файл промпта доступен в контейнере
    print("\n4️⃣  Проверяю доступность файла промпта в контейнере...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app test -f /app/prompts/header_v8.txt && echo 'FILE_EXISTS' || echo 'FILE_NOT_FOUND'")
    print(output)

    if "FILE_EXISTS" in output:
        print("✅ Файл header_v8.txt доступен в контейнере!")
    else:
        print("❌ Файл header_v8.txt не найден!")

    # 5. Проверяем конфигурацию приложения
    print("\n5️⃣  Проверяю конфигурацию приложения...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app python -c \"from invoiceparser.core.config import Config; c = Config.load(); print(f'PROMPT_HEADER_PATH: {c.prompt_header_path}'); print(f'Exists: {c.prompt_header_path.exists()}')\"")
    print(output)

    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    main()

