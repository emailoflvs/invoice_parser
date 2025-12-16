#!/usr/bin/env python3
"""Проверка статуса сборки"""
import sys
import subprocess

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
    project_path = "/opt/docker-projects/invoice_parser"

    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)

        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)

        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            return 1

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("🔍 Проверка процессов сборки:")
        child.sendline('ps aux | grep -E "docker|compose" | grep -v grep | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n📋 Логи сборки (последние 50 строк):")
        child.sendline('tail -50 /tmp/docker_final.log 2>/dev/null || tail -50 /tmp/docker_start_final.log 2>/dev/null || echo "Логи не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n📦 Docker образы:")
        child.sendline('docker images | grep invoice_parser || echo "Образы не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n📊 Все контейнеры:")
        child.sendline('docker ps -a | head -10')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n🌐 Проверка портов:")
        child.sendline('ss -tuln | grep -E ":8000|:5433" || echo "Порты не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

