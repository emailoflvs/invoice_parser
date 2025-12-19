#!/usr/bin/env python3
"""Проверка наличия файла промпта на сервере и исправление имени файла если нужно"""

import pexpect
import sys

SERVER = "debian@57.129.62.58"
PASSWORD = "Polik350"
PROJECT_DIR = "/opt/docker-projects/invoice_parser"
PROMPTS_DIR = f"{PROJECT_DIR}/prompts"

def run_ssh_command(command):
    """Выполнение SSH команды"""
    try:
        child = pexpect.spawn(f'ssh {SERVER} "{command}"', encoding='utf-8', timeout=30)
        child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT])
        if 'password:' in child.before or child.after == 'password:':
            child.sendline(PASSWORD)
        child.expect(pexpect.EOF, timeout=30)
        return child.before.strip()
    except Exception as e:
        print(f"❌ Ошибка выполнения команды: {e}")
        return None

def main():
    print("🔍 Проверяю файлы промптов на сервере...")

    # Проверяем содержимое папки prompts
    result = run_ssh_command(f"ls -la {PROMPTS_DIR}/ | grep header")
    print(f"\n📁 Файлы header в папке prompts:")
    print(result)

    # Проверяем .env на сервере
    print("\n🔍 Проверяю PROMPT_HEADER_PATH в .env...")
    env_result = run_ssh_command(f"grep PROMPT_HEADER_PATH {PROJECT_DIR}/.env")
    print(f"PROMPT_HEADER_PATH: {env_result}")

    # Проверяем, какой файл реально существует
    print("\n🔍 Проверяю наличие файлов...")
    check_v8_underscore = run_ssh_command(f"test -f {PROMPTS_DIR}/header_v8.txt && echo 'EXISTS' || echo 'NOT_FOUND'")
    check_v8_space = run_ssh_command(f"test -f '{PROMPTS_DIR}/header v8.txt' && echo 'EXISTS' || echo 'NOT_FOUND'")

    print(f"header_v8.txt (с подчеркиванием): {check_v8_underscore}")
    print(f"'header v8.txt' (с пробелом): {check_v8_space}")

    # Если файл с пробелом существует, а с подчеркиванием нет - создаем симлинк или копируем
    if "EXISTS" in check_v8_space and "NOT_FOUND" in check_v8_underscore:
        print("\n⚠️  Файл с пробелом существует, но в .env указан с подчеркиванием!")
        print("🔧 Создаю симлинк header_v8.txt -> 'header v8.txt'...")
        result = run_ssh_command(f"cd {PROMPTS_DIR} && ln -sf 'header v8.txt' header_v8.txt")
        print(f"Результат: {result}")

        # Проверяем еще раз
        check_after = run_ssh_command(f"test -f {PROMPTS_DIR}/header_v8.txt && echo 'EXISTS' || echo 'NOT_FOUND'")
        print(f"После создания симлинка: {check_after}")

        if "EXISTS" in check_after:
            print("✅ Симлинк создан успешно!")
        else:
            print("❌ Не удалось создать симлинк")
    elif "EXISTS" in check_v8_underscore:
        print("\n✅ Файл header_v8.txt существует - все в порядке!")
    else:
        print("\n❌ Файл header_v8.txt не найден!")

if __name__ == "__main__":
    main()









