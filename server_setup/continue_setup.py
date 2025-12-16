#!/usr/bin/env python3
"""
Продолжение настройки сервера: установка Docker Compose, UFW и копирование проекта
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
        return 1
    
    print("🚀 Продолжаю настройку сервера...")
    
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
        
        # Установка Docker Compose plugin
        print("\n📦 Установка Docker Compose...")
        child.sendline('docker compose version 2>/dev/null || (echo "Устанавливаю Docker Compose plugin..." && sudo apt-get update && sudo apt-get install -y docker-compose-plugin)')
        
        while True:
            index = child.expect(['password:', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=120)
            if index == 0:
                child.sendline(password)
            elif index in [1, 2]:
                break
            elif index == 3:
                break
            elif index == 4:
                print("Timeout")
                break
        
        # Проверка Docker Compose
        child.sendline('docker compose version')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        # Установка UFW
        print("\n🔥 Установка и настройка firewall...")
        child.sendline('sudo apt-get install -y ufw')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=60)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=60)
        
        # Настройка UFW
        child.sendline('sudo ufw --force enable')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        for port in ['22', '80', '443']:
            child.sendline(f'sudo ufw allow {port}/tcp')
            index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
            if index == 0:
                child.sendline(password)
                child.expect([r'\$ ', r'# '], timeout=10)
        
        # Проверка статуса
        print("\n✅ Проверка установки...")
        child.sendline('docker compose version')
        child.expect([r'\$ ', r'# '], timeout=10)
        child.sendline('sudo ufw status | head -5')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('echo "✅ Настройка завершена"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        print("\n✅ Настройка завершена!")
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

