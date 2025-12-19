#!/usr/bin/env python3
"""Принудительное обновление кода на сервере (с stash локальных изменений)"""

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
        exitstatus = child.exitstatus if hasattr(child, 'exitstatus') else 0
        return output.strip(), exitstatus
    except Exception as e:
        return f"Error: {e}", 1

def main():
    print("🔄 Принудительно обновляю код на сервере...")

    # 1. Stash локальных изменений
    print("\n1️⃣  Сохраняю локальные изменения (stash)...")
    output, _ = run_ssh_command(f"cd {PROJECT_DIR} && git stash")
    print(output)

    # 2. Git pull
    print("\n2️⃣  Выполняю git pull...")
    output, status = run_ssh_command(f"cd {PROJECT_DIR} && git pull")
    print(output)

    # 3. Перезапускаем Docker Compose
    print("\n3️⃣  Перезапускаю Docker Compose...")
    output, status = run_ssh_command(
        f"cd {PROJECT_DIR} && docker compose down && docker compose up -d --build",
        timeout=300
    )
    print(output)

    if status == 0:
        print("\n✅ Приложение обновлено и перезапущено!")
    else:
        print("\n⚠️  Возможны ошибки при перезапуске")

    # 4. Проверяем статус
    print("\n4️⃣  Проверяю статус контейнеров...")
    output, _ = run_ssh_command(f"cd {PROJECT_DIR} && docker compose ps")
    print(output)

    # 5. Проверяем логи
    print("\n5️⃣  Проверяю логи (последние 15 строк)...")
    output, _ = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=15 app")
    print(output)

if __name__ == "__main__":
    main()









