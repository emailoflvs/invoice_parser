#!/usr/bin/env python3
"""Полное исправление проблемы с prompts - пересоздание контейнера"""

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
    print("🔧 Полное исправление проблемы с prompts...")

    # 1. Проверяем права доступа на папку prompts
    print("\n1️⃣  Проверяю права доступа на папку prompts...")
    output = run_ssh_command(f"ls -ld {PROJECT_DIR}/prompts")
    print(output)

    # 2. Проверяем, что файлы действительно есть
    print("\n2️⃣  Проверяю наличие header_v8.txt...")
    output = run_ssh_command(f"test -f {PROJECT_DIR}/prompts/header_v8.txt && echo 'EXISTS' || echo 'NOT_FOUND'")
    print(output)

    # 3. Проверяем текущий docker-compose.yml
    print("\n3️⃣  Проверяю текущий docker-compose.yml (prompts)...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep -n 'prompts' docker-compose.yml | head -5")
    print(output)

    # 4. Останавливаем и удаляем контейнер app
    print("\n4️⃣  Останавливаю и удаляю контейнер app...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose stop app && docker compose rm -f app")
    print(output)

    # 5. Пересоздаем контейнер
    print("\n5️⃣  Пересоздаю контейнер app...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose up -d app", timeout=120)
    print(output)

    # 6. Ждем запуска
    print("\n6️⃣  Жду запуска контейнера (5 секунд)...")
    output = run_ssh_command(f"sleep 5")

    # 7. Проверяем файлы в контейнере
    print("\n7️⃣  Проверяю файлы в контейнере...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose exec -T app ls -la /app/prompts/ | head -15")
    print(output)

    if "header_v8.txt" in output:
        print("\n✅ Проблема исправлена!")
    else:
        print("\n❌ Проблема не решена. Проверяю логи...")
        output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=20 app")
        print(output)

if __name__ == "__main__":
    main()

