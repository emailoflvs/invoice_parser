#!/usr/bin/env python3
"""Тестирование сервера"""
import sys
import subprocess
import requests
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
    server_ip = "57.129.62.58"

    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1

    print("🔍 Проверка статуса сервера...\n")

    try:
        # Подключение
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

        # 1. Проверка контейнеров
        print("1️⃣  Проверка контейнеров:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        # 2. Проверка запущенных контейнеров
        print("\n2️⃣  Запущенные контейнеры:")
        child.sendline('docker ps --format "{{.Names}} - {{.Status}} - {{.Ports}}"')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        # 3. Проверка логов
        print("\n3️⃣  Последние логи приложения:")
        child.sendline('docker compose logs --tail=15 app 2>&1 | tail -20')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        # 4. Проверка БД
        print("\n4️⃣  Статус базы данных:")
        child.sendline('docker compose logs --tail=10 db 2>&1 | tail -15')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        # 5. Проверка портов
        print("\n5️⃣  Проверка портов:")
        child.sendline('ss -tuln 2>/dev/null | grep -E ":8000|:5433" || netstat -tuln 2>/dev/null | grep -E ":8000|:5433" || echo "Порты не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        # 6. Тест HTTP
        print("\n6️⃣  Тест HTTP доступности:")
        child.sendline(f'curl -s -o /dev/null -w "Status: %{{http_code}}, Time: %{{time_total}}s\\n" http://localhost:8000/ 2>&1 || curl -s -o /dev/null -w "Status: %{{http_code}}\\n" http://localhost:8000/health 2>&1 || echo "Приложение не отвечает"')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        # 7. Информация о системе
        print("\n7️⃣  Информация о системе:")
        child.sendline('docker system df')
        child.expect([r'\$ ', r'# '], timeout=10)
        output = child.before
        print(output)

        print("\n" + "="*60)
        print("📊 Итоговая информация:")
        print(f"🌐 Внешний доступ: http://{server_ip}:8000")
        print(f"📁 Проект: {project_path}")
        print("="*60)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        # Попытка внешнего теста
        print("\n🌐 Тест внешнего доступа:")
        try:
            response = requests.get(f'http://{server_ip}:8000/', timeout=5)
            print(f"✅ HTTP {response.status_code} - Приложение доступно!")
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Внешний доступ: {e}")
            print("   (Возможно, приложение еще запускается или порт не открыт)")

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

