#!/usr/bin/env python3
"""Загрузка необходимых файлов на сервер через SSH"""
import sys
import subprocess
from pathlib import Path

def install_pexpect():
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
    local_path = Path("/home/lvs/Desktop/AI/servers/invoice_parser")

    # Файлы для копирования
    files_to_copy = [
        '.env',
        'google_sheets_credentials.json',
    ]

    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1

    print("📤 Загрузка файлов на сервер...")

    copied = []
    missing = []

    for file_name in files_to_copy:
        local_file = local_path / file_name
        if local_file.exists():
            print(f"\n📄 Копирую {file_name}...")
            try:
                child = pexpect.spawn(f'scp -o StrictHostKeyChecking=no {local_file} {server}:{server_path}/{file_name}',
                                    encoding='utf-8', timeout=30)
                child.logfile = None  # Не показываем вывод scp

                index = child.expect(['password:', 'Permission denied', pexpect.EOF, pexpect.TIMEOUT], timeout=30)

                if index == 0:
                    child.sendline(password)
                    child.expect(pexpect.EOF, timeout=30)
                    print(f"  ✅ {file_name} успешно скопирован")
                    copied.append(file_name)
                elif index == 1:
                    print(f"  ❌ Ошибка доступа для {file_name}")
                    missing.append(file_name)
                else:
                    print(f"  ✅ {file_name} скопирован")
                    copied.append(file_name)
            except Exception as e:
                print(f"  ❌ Ошибка при копировании {file_name}: {e}")
                missing.append(file_name)
        else:
            print(f"  ⚠️  Файл {file_name} не найден локально")
            missing.append(file_name)

    # Проверка на сервере
    print("\n🔍 Проверка файлов на сервере...")
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

        child.sendline(f'cd {server_path} && ls -lh .env google_sheets_credentials.json 2>/dev/null')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
    except Exception as e:
        print(f"⚠️  Не удалось проверить файлы: {e}")

    print("\n" + "="*50)
    print("📊 Итоги:")
    if copied:
        print(f"✅ Успешно скопировано: {', '.join(copied)}")
    if missing:
        print(f"⚠️  Не скопировано: {', '.join(missing)}")
    print("="*50)

    return 0 if not missing else 1

if __name__ == "__main__":
    sys.exit(main())









