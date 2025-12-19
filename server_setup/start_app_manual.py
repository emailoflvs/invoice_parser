#!/usr/bin/env python3
"""Ручной запуск приложения и проверка"""
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
        print(f"❌ Ошибка: {e}")
        return 1
    
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout
        
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        
        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ЗАПУСК ПРИЛОЖЕНИЯ ===")
        child.sendline('docker compose up -d app')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        print("\n⏳ Ожидание 30 секунд...")
        time.sleep(30)
        
        print("\n=== СТАТУС ===")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ЛОГИ ПРИЛОЖЕНИЯ ===")
        child.sendline('docker compose logs app --tail=50')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ПОРТЫ ===")
        child.sendline('ss -tuln | grep 8000')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ТЕСТ HTTP ===")
        child.sendline('curl -s -I http://localhost:8000/ 2>&1 | head -5')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())









