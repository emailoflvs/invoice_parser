#!/usr/bin/env python3
"""Запуск сервера в фоне с последующей проверкой"""
import sys
import subprocess
import time

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

    print("🚀 Запуск сервера в фоне...\n")

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

        # Остановка существующих
        print("🛑 Остановка существующих контейнеров...")
        child.sendline('docker compose down 2>/dev/null || true')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Запуск в фоне
        print("🔨 Запуск сборки и контейнеров в фоне...")
        print("   (Это может занять 5-10 минут)")
        child.sendline('nohup docker compose up -d --build > /tmp/docker_build.log 2>&1 &')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка процесса
        child.sendline('sleep 2 && ps aux | grep "docker compose" | grep -v grep | head -2')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n✅ Сборка запущена в фоне")
        print("\n⏳ Подождите 5-10 минут, затем проверьте статус:")
        print(f"   ssh {server}")
        print(f"   cd {project_path}")
        print("   docker compose ps")
        print("   docker compose logs -f")
        print("\n📋 Или используйте скрипт проверки:")
        print("   python3 server_setup/test_server.py")

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        # Ждем немного и проверяем начальный статус
        print("\n⏳ Ожидание 60 секунд для начала сборки...")
        time.sleep(60)

        print("\n🔍 Первичная проверка статуса...")
        child2 = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        index = child2.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child2.sendline(password)
            child2.expect([r'\$ ', r'# '], timeout=15)

        child2.sendline(f'cd {project_path} && docker compose ps')
        child2.expect([r'\$ ', r'# '], timeout=10)

        child2.sendline('tail -20 /tmp/docker_build.log 2>/dev/null || echo "Логи еще не созданы"')
        child2.expect([r'\$ ', r'# '], timeout=10)

        child2.sendline('exit')
        child2.expect(pexpect.EOF, timeout=5)

        print("\n" + "="*60)
        print("✅ Сборка запущена!")
        print("   Проверьте статус через несколько минут")
        print("="*60)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())









