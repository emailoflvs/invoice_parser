#!/usr/bin/env python3
"""Проверка и исправление проблем"""
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
    
    print("🔍 Проверка и исправление проблем...\n")
    
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
        
        # Проверка процессов
        print("1️⃣  Проверка процессов Docker:")
        child.sendline('ps aux | grep -E "docker|compose" | grep -v grep | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка логов сборки
        print("\n2️⃣  Логи сборки (последние 50 строк):")
        child.sendline('tail -50 /tmp/docker_full_restart.log 2>/dev/null || echo "Логи не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка образов
        print("\n3️⃣  Docker образы:")
        child.sendline('docker images | grep invoice_parser || echo "Образы не найдены"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка контейнеров
        print("\n4️⃣  Все контейнеры:")
        child.sendline('docker ps -a | head -10')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Если контейнеры не запущены, запускаем заново
        print("\n5️⃣  Проверка статуса docker compose:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Если ничего не запущено, запускаем
        print("\n6️⃣  Запуск если не запущено...")
        child.sendline('if ! docker compose ps | grep -q "Up"; then echo "Запускаю..."; docker compose up -d --build 2>&1 | tail -20; else echo "Уже запущено"; fi')
        child.expect([r'\$ ', r'# '], timeout=120)
        
        # Ждем
        print("\n⏳ Ожидание 30 секунд...")
        time.sleep(30)
        
        # Финальная проверка
        print("\n7️⃣  Финальная проверка:")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n8️⃣  Проверка портов:")
        child.sendline('ss -tuln | grep ":8000" && echo "✅ Порт 8000 открыт" || echo "❌ Порт 8000 не открыт"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n9️⃣  Логи приложения (последние 20 строк):")
        child.sendline('docker compose logs --tail=20 2>&1 | tail -25')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n🔟 Тест HTTP:")
        child.sendline('curl -s -I http://localhost:8000/ 2>&1 | head -5 || echo "Приложение не отвечает"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n" + "="*60)
        print("✅ Проверка завершена!")
        print("="*60)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

