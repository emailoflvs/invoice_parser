#!/usr/bin/env python3
"""
Развертывание проекта через Git + копирование дополнительных файлов
"""
import sys
import subprocess
import os
from pathlib import Path

def install_pexpect():
    """Установка pexpect если его нет"""
    try:
        import pexpect
        return pexpect
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pexpect", "--user", "-q"])
        import pexpect
        return pexpect

def main():
    server = "debian@57.129.62.58"
    password = "Polik350"
    server_path = "/opt/docker-projects/invoice_parser"
    git_repo = "git@github.com:emailoflvs/invoice_parser.git"
    local_path = "/home/lvs/Desktop/AI/servers/invoice_parser"

    # Файлы, которые нужно скопировать дополнительно (не в git)
    additional_files = [
        '.env',
        'google_sheets_credentials.json',
    ]

    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1

    print("🚀 Развертывание проекта через Git...")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)

        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            return 1

        print("✅ Подключен к серверу")

        # Проверка и установка git
        print("\n📦 Проверка Git...")
        child.sendline('which git || (echo "Устанавливаю Git..." && sudo apt-get update && sudo apt-get install -y git)')

        while True:
            index = child.expect(['password:', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=60)
            if index == 0:
                child.sendline(password)
            elif index in [1, 2]:
                break
            elif index == 3:
                break
            elif index == 4:
                break

        # Создание директории
        print("\n📁 Создание директории проекта...")
        child.sendline(f'sudo mkdir -p {server_path} && sudo chown -R debian:debian {server_path}')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        # Клонирование репозитория
        print("\n📥 Клонирование/обновление репозитория...")
        git_repo_https = "https://github.com/emailoflvs/invoice_parser.git"

        # Проверяем, есть ли уже git репозиторий
        child.sendline(f'cd {server_path} && if [ -d .git ]; then echo "Репозиторий существует, обновляю..."; git pull origin main || git pull; else echo "Клонирую репозиторий..."; git clone {git_repo_https} . || (rm -rf * .[^.]* 2>/dev/null; git clone {git_repo_https} .); fi')

        # Ждем завершения
        while True:
            index = child.expect([
                'Are you sure you want to continue connecting',
                'Already up to date',
                'Updating',
                'Cloning',
                'fatal:',
                r'\$ ',
                r'# ',
                pexpect.EOF,
                pexpect.TIMEOUT
            ], timeout=120)

            if index == 0:
                child.sendline('yes')
            elif index in [1, 2, 3]:
                # Продолжаем ждать
                continue
            elif index == 4:
                # Ошибка, пробуем очистить и клонировать заново
                print("\n⚠️  Ошибка, очищаю и клонирую заново...")
                child.sendline(f'cd {server_path} && rm -rf * .[^.]* 2>/dev/null; git clone {git_repo_https} .')
                child.expect([r'\$ ', r'# '], timeout=120)
                break
            elif index in [5, 6]:
                break
            elif index == 7:
                break
            elif index == 8:
                break

        print("✅ Репозиторий клонирован/обновлен")

        # Проверка файлов
        child.sendline(f'cd {server_path} && ls -la | head -10')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        # Копирование дополнительных файлов
        print("\n📤 Копирование дополнительных файлов...")
        for file_name in additional_files:
            local_file = Path(local_path) / file_name
            if local_file.exists():
                print(f"  Копирую {file_name}...")
                child = pexpect.spawn(f'scp -o StrictHostKeyChecking=no {local_file} {server}:{server_path}/{file_name}', encoding='utf-8', timeout=30)
                child.logfile = None  # Не показываем вывод scp

                index = child.expect(['password:', 'Permission denied', pexpect.EOF, pexpect.TIMEOUT], timeout=30)

                if index == 0:
                    child.sendline(password)
                    child.expect(pexpect.EOF, timeout=30)
                    print(f"  ✅ {file_name} скопирован")
                elif index == 1:
                    print(f"  ⚠️  Не удалось скопировать {file_name}")
            else:
                print(f"  ⚠️  Файл {file_name} не найден локально, пропускаю")

        print("\n✅ Развертывание завершено!")
        print(f"\n📝 Следующие шаги:")
        print(f"   ssh {server}")
        print(f"   cd {server_path}")
        print("   # Проверьте/создайте .env файл если нужно")
        print("   docker compose up -d --build")

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

