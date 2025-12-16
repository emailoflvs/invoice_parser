#!/usr/bin/env python3
"""Запуск и полное тестирование приложения"""
import sys
import subprocess
import time
import requests

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
        print(f"❌ Ошибка: {e}")
        return 1

    print("🚀 Запуск и тестирование приложения...\n")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)

        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("1️⃣  ОБНОВЛЕНИЕ КОДА")
        print("="*60)
        child.sendline('git pull origin main')
        child.expect([r'\$ ', r'# '], timeout=30)

        print("\n" + "="*60)
        print("2️⃣  ОСТАНОВКА КОНТЕЙНЕРОВ")
        print("="*60)
        child.sendline('docker compose down')
        child.expect([r'\$ ', r'# '], timeout=30)

        print("\n" + "="*60)
        print("3️⃣  ЗАПУСК ПРИЛОЖЕНИЯ")
        print("="*60)
        child.sendline('docker compose up -d --build app')

        max_wait = 300
        start = time.time()
        while time.time() - start < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=120)
                if index in [0, 1]:
                    break
            except:
                continue

        print("\n⏳ Ожидание 90 секунд для запуска приложения...")
        time.sleep(90)

        print("\n" + "="*60)
        print("4️⃣  СТАТУС КОНТЕЙНЕРОВ")
        print("="*60)
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("5️⃣  ПРОВЕРКА ПОРТОВ")
        print("="*60)
        child.sendline('ss -tuln | grep 8000')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("6️⃣  ЛОГИ ПРИЛОЖЕНИЯ (последние 30 строк)")
        print("="*60)
        child.sendline('docker compose logs app --tail=30')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("7️⃣  ТЕСТ HTTP (локально на сервере)")
        print("="*60)
        child.sendline('curl -s -o /dev/null -w "HTTP Status: %{http_code}\nTime: %{time_total}s\n" http://localhost:8000/ 2>&1')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("8️⃣  ПРОВЕРКА ПРОЦЕССОВ")
        print("="*60)
        child.sendline('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep invoiceparser')
        child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)

        # Тест внешнего доступа
        print("\n" + "="*60)
        print("9️⃣  ТЕСТ ВНЕШНЕГО ДОСТУПА")
        print("="*60)
        print("Проверка внешнего доступа...")
        try:
            response = requests.get("http://57.129.62.58:8000/", timeout=10)
            print(f"✅ Внешний доступ: HTTP {response.status_code}")
            if response.status_code == 200:
                print(f"   Размер ответа: {len(response.content)} байт")
                print(f"   Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        except requests.exceptions.ConnectionError:
            print("❌ Внешний доступ: Connection refused")
        except requests.exceptions.Timeout:
            print("❌ Внешний доступ: Timeout")
        except Exception as e:
            print(f"❌ Внешний доступ: {e}")

        print("\n" + "="*60)
        print("✅ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
        print("="*60)
        print("\n🌐 Проверьте сайт:")
        print("   http://doclogic.eu")
        print("   http://57.129.62.58:8000")
        print("\n📋 Полезные команды:")
        print("   docker compose logs -f app    # Логи в реальном времени")
        print("   docker compose ps              # Статус контейнеров")
        print("   docker compose restart app     # Перезапуск приложения")
        print("="*60)

        return 0

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

