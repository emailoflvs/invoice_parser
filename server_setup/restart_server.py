#!/usr/bin/env python3
"""Перезапуск сервера с проверкой"""
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

    print("🚀 Перезапуск сервера...\n")

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

        # Проверка логов предыдущей сборки
        print("📋 Проверка логов предыдущей сборки:")
        child.sendline('tail -50 /tmp/docker_start.log 2>/dev/null | tail -30 || echo "Логи не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Остановка всех контейнеров
        print("\n🛑 Остановка контейнеров...")
        child.sendline('docker compose down')
        child.expect([r'\$ ', r'# '], timeout=30)

        # Очистка старых образов (опционально)
        print("\n🧹 Очистка...")
        child.sendline('docker compose down -v 2>/dev/null || true')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Запуск
        print("\n🔨 Запуск Docker Compose...")
        print("   (Это может занять 5-10 минут для первой сборки)")
        child.sendline('docker compose up -d --build 2>&1 | tee /tmp/docker_build.log')

        # Ждем завершения команды
        max_wait = 600  # 10 минут
        import time
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=60)
                if index in [0, 1]:
                    break
            except pexpect.TIMEOUT:
                # Продолжаем ждать
                print("   ⏳ Сборка продолжается...")
                continue

        print("\n✅ Команда завершена")

        # Проверка статуса
        print("\n📊 Статус контейнеров:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Логи
        print("\n📋 Логи (последние 30 строк):")
        child.sendline('docker compose logs --tail=30 2>&1 | tail -40')
        child.expect([r'\$ ', r'# '], timeout=10)

        # Проверка портов
        print("\n🌐 Проверка портов:")
        child.sendline('ss -tuln | grep -E ":8000|:5433" || echo "Порты не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("✅ Сервер перезапущен!")
        print("="*60)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())









