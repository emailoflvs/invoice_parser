#!/usr/bin/env python3
"""
Автоматическая настройка сервера через SSH
"""
import sys
import subprocess
import os

def install_pexpect():
    """Установка pexpect если его нет"""
    try:
        import pexpect
        return pexpect
    except ImportError:
        print("Устанавливаю pexpect...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pexpect", "--user", "-q"])
        import pexpect
        return pexpect

def main():
    server = "debian@57.129.62.58"
    password = "Polik350"
    
    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        print("Попробуйте установить вручную: pip install pexpect")
        return 1
    
    print("🚀 Начинаю автоматическую настройку сервера...")
    
    # Подключение к серверу
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout
        
        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            return 1
        elif index in [2, 3]:
            # Уже подключен
            pass
        else:
            print("❌ Не удалось подключиться")
            return 1
        
        print("✅ Подключен к серверу")
        
        # Проверка системы
        print("\n📊 Проверка системы...")
        child.sendline('echo "=== Системная информация ==="')
        child.expect([r'\$ ', r'# '], timeout=10)
        child.sendline('uname -a')
        child.expect([r'\$ ', r'# '], timeout=10)
        child.sendline('df -h | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)
        child.sendline('free -h')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка Docker
        print("\n🐳 Проверка Docker...")
        child.sendline('docker --version 2>/dev/null || echo "Docker не установлен"')
        child.expect([r'\$ ', r'# '], timeout=10)
        child.sendline('docker-compose --version 2>/dev/null || echo "Docker Compose не установлен"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Установка Docker если нужно
        print("\n📦 Установка Docker (если нужно)...")
        child.sendline('if ! command -v docker &> /dev/null; then echo "Устанавливаю Docker..."; curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh; fi')
        
        # Обработка sudo пароля
        while True:
            index = child.expect(['password:', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=120)
            if index == 0:
                child.sendline(password)
            elif index in [1, 2]:
                break
            elif index == 3:
                print("Соединение закрыто")
                break
            elif index == 4:
                print("Timeout при установке Docker")
                break
        
        # Добавление пользователя в группу docker
        print("\n👤 Настройка прав доступа...")
        child.sendline('sudo usermod -aG docker debian 2>/dev/null || true')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        # Создание структуры директорий
        print("\n📁 Создание структуры директорий...")
        child.sendline('sudo mkdir -p /opt/docker-projects/invoice_parser')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('sudo chown -R debian:debian /opt/docker-projects')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        # Настройка firewall
        print("\n🔥 Настройка firewall...")
        for port in ['22', '80', '443']:
            child.sendline(f'sudo ufw allow {port}/tcp')
            index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
            if index == 0:
                child.sendline(password)
                child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('echo "✅ Базовая настройка завершена"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        print("\n✅ Настройка сервера завершена!")
        return 0
        
    except pexpect.exceptions.TIMEOUT:
        print("❌ Timeout при подключении")
        return 1
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

