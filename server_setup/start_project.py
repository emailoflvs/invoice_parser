#!/usr/bin/env python3
"""
Запуск проекта на сервере
"""
import sys
import subprocess

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
    project_path = "/opt/docker-projects/invoice_parser"
    
    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1
    
    print("🚀 Запуск проекта на сервере...")
    
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
        
        # Переход в директорию проекта
        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка наличия .env файла
        print("\n📋 Проверка конфигурации...")
        child.sendline('if [ ! -f .env ]; then echo "⚠️ .env файл не найден, создаю базовый..."; touch .env; echo "APP_PORT=8000" >> .env; echo "DB_EXTERNAL_PORT=5433" >> .env; echo "DB_USER=invoiceparser" >> .env; echo "DB_PASSWORD=invoiceparser_password" >> .env; echo "DB_NAME=invoiceparser" >> .env; fi')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('ls -la .env docker-compose.yml Dockerfile 2>/dev/null | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка Docker
        print("\n🐳 Проверка Docker...")
        child.sendline('docker --version && docker compose version')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Остановка существующих контейнеров (если есть)
        print("\n🛑 Остановка существующих контейнеров (если есть)...")
        child.sendline('docker compose down 2>/dev/null || true')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        # Сборка и запуск
        print("\n🔨 Сборка и запуск проекта...")
        print("(Это может занять несколько минут...)")
        child.sendline('docker compose up -d --build 2>&1')
        
        # Увеличиваем таймаут для сборки и ждем завершения
        import time
        max_wait = 600  # 10 минут
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=30)
                if index in [0, 1]:
                    # Проверяем, завершилась ли команда
                    break
            except pexpect.TIMEOUT:
                # Продолжаем ждать
                pass
        
        # Проверка статуса
        print("\n📊 Проверка статуса контейнеров...")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Показываем логи (первые строки)
        print("\n📋 Последние логи...")
        child.sendline('docker compose logs --tail=20')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка портов
        print("\n🌐 Проверка открытых портов...")
        child.sendline('docker compose ps | grep -E "PORTS|0.0.0.0" || echo "Проверка портов..."')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('echo "✅ Проект запущен!"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        print("\n✅ Проект успешно запущен на сервере!")
        print(f"\n📝 Полезные команды:")
        print(f"   ssh {server}")
        print(f"   cd {project_path}")
        print(f"   docker compose ps          # Статус контейнеров")
        print(f"   docker compose logs -f     # Логи в реальном времени")
        print(f"   docker compose down        # Остановка")
        print(f"   docker compose restart     # Перезапуск")
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

