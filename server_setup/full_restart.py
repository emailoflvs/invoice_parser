#!/usr/bin/env python3
"""Полный перезапуск с исправленной миграцией"""
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
    
    print("🚀 Полный перезапуск сервера с исправленной миграцией...\n")
    
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
        
        # 1. Обновление из Git
        print("1️⃣  Обновление кода из Git...")
        child.sendline('git pull origin main')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        # 2. Остановка и очистка
        print("\n2️⃣  Остановка контейнеров и очистка...")
        child.sendline('docker compose down -v')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        # 3. Очистка старых образов (опционально)
        print("\n3️⃣  Очистка старых образов...")
        child.sendline('docker system prune -f --volumes 2>/dev/null || true')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        # 4. Открытие порта
        print("\n4️⃣  Открытие порта 8000 в firewall...")
        child.sendline('sudo ufw allow 8000/tcp 2>/dev/null || true')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        # 5. Запуск в фоне
        print("\n5️⃣  Запуск приложения (это займет 5-10 минут)...")
        child.sendline('nohup docker compose up -d --build > /tmp/docker_full_restart.log 2>&1 &')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("✅ Команда запущена в фоне")
        print("\n⏳ Ожидание 120 секунд для сборки и запуска...")
        time.sleep(120)
        
        # 6. Проверка статуса
        print("\n6️⃣  Проверка статуса контейнеров:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # 7. Проверка логов
        print("\n7️⃣  Последние логи (50 строк):")
        child.sendline('docker compose logs --tail=50 2>&1 | tail -60')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # 8. Проверка портов
        print("\n8️⃣  Проверка портов:")
        child.sendline('ss -tuln | grep -E ":8000|:5433" || echo "Порты не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # 9. Тест HTTP
        print("\n9️⃣  Тест HTTP доступности:")
        child.sendline('curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://localhost:8000/ 2>&1 || echo "Приложение не отвечает"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # 10. Проверка логов сборки
        print("\n🔟 Проверка логов сборки (последние 30 строк):")
        child.sendline('tail -30 /tmp/docker_full_restart.log 2>/dev/null || echo "Логи не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # 11. Информация о контейнерах
        print("\n1️⃣1️⃣  Информация о контейнерах:")
        child.sendline('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n" + "="*60)
        print("✅ Перезапуск завершен!")
        print("\n🌐 Проверьте сайт:")
        print("   http://doclogic.eu")
        print("   http://57.129.62.58:8000")
        print("\n📋 Полезные команды:")
        print("   docker compose logs -f          # Логи в реальном времени")
        print("   docker compose ps               # Статус контейнеров")
        print("   docker compose restart          # Перезапуск")
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










