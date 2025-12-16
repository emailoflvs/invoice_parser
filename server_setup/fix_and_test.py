#!/usr/bin/env python3
"""Исправление проблем и тестирование"""
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
    
    print("🔧 Исправление проблем и тестирование...\n")
    
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout
        
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        
        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ИСПРАВЛЕНИЕ GIT ===")
        child.sendline('git stash && git pull origin main')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        print("\n=== ПРОВЕРКА ЛОГОВ ПРИЛОЖЕНИЯ (после миграций) ===")
        child.sendline('docker compose logs app --tail=50 | grep -A 10 "Starting application" || docker compose logs app --tail=50 | tail -20')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ПРОВЕРКА ОШИБОК ===")
        child.sendline('docker compose logs app --tail=100 | grep -iE "error|exception|traceback|failed" | tail -20 || echo "Ошибок не найдено"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== СТАТУС ===")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

