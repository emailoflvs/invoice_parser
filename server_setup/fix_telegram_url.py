#!/usr/bin/env python3
"""Исправление URL для Telegram бота - добавление WEB_PUBLIC_URL в .env"""

import pexpect

SERVER = "debian@57.129.62.58"
PASSWORD = "Polik350"
PROJECT_DIR = "/opt/docker-projects/invoice_parser"
PUBLIC_URL = "https://doclogic.eu"

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
    print("🔧 Исправляю URL для Telegram бота...")

    # 1. Проверяем текущий .env
    print("\n1️⃣  Проверяю WEB_PUBLIC_URL в .env...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep WEB_PUBLIC_URL .env || echo 'NOT_FOUND'")
    print(output)

    # 2. Добавляем или обновляем WEB_PUBLIC_URL
    if "NOT_FOUND" in output or not output.strip():
        print("\n2️⃣  Добавляю WEB_PUBLIC_URL в .env...")
        # Добавляем в конец файла
        result = run_ssh_command(f"cd {PROJECT_DIR} && echo '' >> .env && echo '# Public URL for Telegram bot links' >> .env && echo 'WEB_PUBLIC_URL={PUBLIC_URL}' >> .env")
        print("✅ WEB_PUBLIC_URL добавлен")
    else:
        print("\n2️⃣  Обновляю WEB_PUBLIC_URL в .env...")
        # Заменяем существующую строку
        result = run_ssh_command(f"cd {PROJECT_DIR} && sed -i 's|^WEB_PUBLIC_URL=.*|WEB_PUBLIC_URL={PUBLIC_URL}|' .env")
        print("✅ WEB_PUBLIC_URL обновлен")

    # 3. Проверяем результат
    print("\n3️⃣  Проверяю результат...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && grep WEB_PUBLIC_URL .env")
    print(output)

    # 4. Перезапускаем telegram-bot контейнер
    print("\n4️⃣  Перезапускаю telegram-bot контейнер...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose restart telegram-bot", timeout=60)
    print(output)

    # 5. Проверяем логи
    print("\n5️⃣  Проверяю логи telegram-bot (последние 10 строк)...")
    output = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=10 telegram-bot")
    print(output)

    print("\n✅ Готово! Теперь ссылки в Telegram будут вести на публичный URL.")

if __name__ == "__main__":
    main()










