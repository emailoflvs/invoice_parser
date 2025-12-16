#!/usr/bin/env python3
"""Полный перезапуск с обновленным кодом"""
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
    
    print("🔄 Полный перезапуск с исправленной миграцией...\n")
    
    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout
        
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        
        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ОБНОВЛЕНИЕ КОДА ===")
        child.sendline('git pull origin main')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        print("\n=== ПРОВЕРКА ИСПРАВЛЕНИЯ ===")
        child.sendline('grep -A 2 "CREATE TABLE document_table_sections" alembic/versions/004_partition_related_tables.py | grep -i "foreign key" || echo "✅ FK убран"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n=== ОСТАНОВКА И ОЧИСТКА БД ===")
        child.sendline('docker compose down -v')
        child.expect([r'\$ ', r'# '], timeout=30)
        
        print("\n=== ЗАПУСК ===")
        child.sendline('docker compose up -d --build')
        
        max_wait = 600
        start = time.time()
        while time.time() - start < max_wait:
            try:
                index = child.expect([r'\$ ', r'# ', pexpect.TIMEOUT], timeout=120)
                if index in [0, 1]:
                    break
            except:
                continue
        
        print("\n⏳ Ожидание 90 секунд...")
        time.sleep(90)
        
        print("\n=== ФИНАЛЬНАЯ ПРОВЕРКА ===")
        child.sendline('docker compose ps')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('docker compose logs app --tail=30')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('ss -tuln | grep 8000 && echo "✅" || echo "❌"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ 2>&1 || echo "не отвечает"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

