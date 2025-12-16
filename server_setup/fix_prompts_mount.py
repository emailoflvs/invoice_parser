#!/usr/bin/env python3
"""Исправление проблемы с монтированием prompts"""

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
    print("🔧 Исправляю проблему с монтированием prompts...")

    # 1. Проверяем .env на сервере
    print("\n1️⃣  Проверяю PROMPTS_DIR в .env...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep PROMPTS_DIR .env")
    print(output)

    # 2. Проверяем docker-compose.yml
    print("\n2️⃣  Проверяю docker-compose.yml...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep -A 2 PROMPTS_DIR docker-compose.yml")
    print(output)

    # 3. Проверяем, что файлы есть на хосте
    print("\n3️⃣  Проверяю наличие файлов на хосте...")
    output = run_ssh_command(f"ls -la {PROJECT_DIR}/prompts/header_v8.txt")
    print(output)

    # 4. Исправляем docker-compose.yml - используем абсолютный путь
    print("\n4️⃣  Исправляю docker-compose.yml - заменяю на абсолютный путь...")

    # Читаем текущий docker-compose.yml
    output = run_ssh_command(f"cd {PROJECT_DIR} && cat docker-compose.yml | grep -A 1 'PROMPTS_DIR' | head -2")
    print(f"Текущая строка: {output}")

    # Заменяем относительный путь на абсолютный
    replace_cmd = f"cd {PROJECT_DIR} && sed -i 's|\\${{PROMPTS_DIR:-./prompts}}:/app/prompts|{PROJECT_DIR}/prompts:/app/prompts|g' docker-compose.yml"
    result = run_ssh_command(replace_cmd)
    print(f"Результат замены: {result}")

    # 5. Проверяем результат
    print("\n5️⃣  Проверяю результат...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep 'prompts:/app/prompts' docker-compose.yml")
    print(output)

    # 6. Перезапускаем контейнер
    print("\n6️⃣  Перезапускаю контейнер app...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose restart app", timeout=60)
    print(output)

    # 7. Проверяем файлы в контейнере
    print("\n7️⃣  Проверяю файлы в контейнере после перезапуска...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && sleep 3 && docker compose exec -T app ls -la /app/prompts/ | head -10")
    print(output)

    if "header_v8.txt" in output:
        print("\n✅ Проблема исправлена! Файлы теперь доступны в контейнере.")
    else:
        print("\n⚠️  Файлы все еще не видны. Попробуем другой подход.")

if __name__ == "__main__":
    main()

