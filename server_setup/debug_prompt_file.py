#!/usr/bin/env python3
"""Отладка проблемы с файлом промпта на сервере"""

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
    print("🔍 Отладка проблемы с файлом промпта на сервере...")

    # 1. Проверяем файл на хосте
    print("\n1️⃣  Проверяю файл на хосте сервера...")
    output = run_ssh_command(f"ls -la {PROJECT_DIR}/prompts/header_v8.txt")
    print(output)

    # 2. Проверяем файл в контейнере
    print("\n2️⃣  Проверяю файл в контейнере...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app ls -la /app/prompts/header_v8.txt")
    print(output)

    # 3. Проверяем все файлы в папке prompts в контейнере
    print("\n3️⃣  Проверяю все файлы в /app/prompts/ в контейнере...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app ls -la /app/prompts/ | head -20")
    print(output)

    # 4. Проверяем PROMPT_HEADER_PATH в .env
    print("\n4️⃣  Проверяю PROMPT_HEADER_PATH в .env...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep PROMPT_HEADER_PATH .env")
    print(output)

    # 5. Проверяем, что пытается открыть приложение (из логов)
    print("\n5️⃣  Проверяю последние логи с ошибками...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=30 app | grep -i 'prompt\|header_v8\|E006'")
    print(output)

    # 6. Проверяем путь, который используется в коде
    print("\n6️⃣  Проверяю путь в конфиге приложения...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app python -c \"from invoiceparser.core.config import Config; c = Config.load(); print(f'PROMPT_HEADER_PATH: {{c.prompt_header_path}}'); print(f'Exists: {{c.prompt_header_path.exists()}}')\"")
    print(output)

    # 7. Проверяем docker-compose.yml - как монтируются prompts
    print("\n7️⃣  Проверяю docker-compose.yml - монтирование prompts...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep -A 5 -B 5 prompts docker-compose.yml")
    print(output)

if __name__ == "__main__":
    main()










