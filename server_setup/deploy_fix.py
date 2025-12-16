#!/usr/bin/env python3
"""Копирование исправленных файлов на сервер и перезапуск"""

import pexpect
import subprocess
import sys

SERVER = "debian@57.129.62.58"
PASSWORD = "Polik350"
PROJECT_DIR = "/opt/docker-projects/invoice_parser"

FILES_TO_COPY = [
    ("src/invoiceparser/services/gemini_client.py", f"{PROJECT_DIR}/src/invoiceparser/services/gemini_client.py"),
    ("src/invoiceparser/adapters/web_api.py", f"{PROJECT_DIR}/src/invoiceparser/adapters/web_api.py"),
    ("static/script.js", f"{PROJECT_DIR}/static/script.js"),
]

def run_scp(local_path, remote_path):
    """Копирование файла через SCP"""
    try:
        child = pexpect.spawn(f'scp {local_path} {SERVER}:{remote_path}', encoding='utf-8', timeout=30)
        index = child.expect(['password:', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(PASSWORD)
            child.expect(pexpect.EOF, timeout=30)
        return child.exitstatus == 0
    except Exception as e:
        print(f"❌ Ошибка при копировании {local_path}: {e}")
        return False

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
    print("📦 Копирую исправленные файлы на сервер...")

    for local_file, remote_file in FILES_TO_COPY:
        print(f"\n📄 Копирую {local_file}...")
        if run_scp(local_file, remote_file):
            print(f"✅ {local_file} скопирован")
        else:
            print(f"❌ Ошибка при копировании {local_file}")
            return

    print("\n🔄 Перезапускаю контейнер app...")
    output, status = run_ssh_command(
        f"cd {PROJECT_DIR} && docker compose restart app",
        timeout=60
    )
    print(output)

    if status == 0:
        print("\n✅ Приложение перезапущено!")
    else:
        print("\n⚠️  Возможны ошибки при перезапуске")

    # Проверяем логи
    print("\n📋 Проверяю логи (последние 10 строк)...")
    output, _ = run_ssh_command(f"cd {PROJECT_DIR} && docker compose logs --tail=10 app")
    print(output)

if __name__ == "__main__":
    main()

