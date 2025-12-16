#!/usr/bin/env python3
"""Запуск проекта в фоне"""
import sys
import subprocess

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
        
        child.sendline(f'cd {project_path}')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("\n🔨 Запускаю сборку и запуск проекта в фоне...")
        print("(Это может занять 5-10 минут)")
        
        # Запускаем в фоне через nohup
        child.sendline('nohup docker compose up -d --build > /tmp/docker_build.log 2>&1 &')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        print("✅ Команда запущена в фоне")
        print("\n💡 Проверьте статус через несколько минут:")
        print(f"   ssh {server}")
        print(f"   cd {project_path}")
        print("   docker compose ps")
        print("   docker compose logs -f")
        
        child.sendline('echo "Процесс запущен, PID: $(pgrep -f \"docker compose\")"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

