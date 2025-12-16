#!/usr/bin/env python3
"""
Копирование файлов проекта на сервер
"""
import sys
import subprocess
import os
import tarfile
import tempfile
from pathlib import Path

def install_pexpect():
    """Установка pexpect если его нет"""
    try:
        import pexpect
        return pexpect
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pexpect", "--user", "-q"])
        import pexpect
        return pexpect

def create_tarball(source_dir, exclude_patterns):
    """Создание tar архива с исключениями"""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tar.gz')
    temp_path = temp_file.name
    temp_file.close()
    
    print(f"📦 Создание архива...")
    
    with tarfile.open(temp_path, 'w:gz') as tar:
        source = Path(source_dir)
        for item in source.rglob('*'):
            # Пропускаем исключения
            skip = False
            for pattern in exclude_patterns:
                if pattern in str(item.relative_to(source)):
                    skip = True
                    break
            if skip:
                continue
            
            if item.is_file():
                try:
                    tar.add(item, arcname=item.relative_to(source))
                except Exception as e:
                    print(f"Пропущен {item}: {e}")
    
    return temp_path

def main():
    server = "debian@57.129.62.58"
    password = "Polik350"
    server_path = "/opt/docker-projects/invoice_parser"
    local_path = "/home/lvs/Desktop/AI/servers/invoice_parser"
    
    exclude_patterns = [
        'venv/',
        '__pycache__/',
        '*.pyc',
        '.git/',
        '*.log',
        'temp/',
        'output/arch/',
        'output/temp/',
        'output/prompt_tests/',
        'output/v6/',
        'node_modules/',
        '.env'
    ]
    
    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Не удалось установить pexpect: {e}")
        return 1
    
    print("🚀 Копирование проекта на сервер...")
    
    # Создаем архив
    try:
        archive_path = create_tarball(local_path, exclude_patterns)
        print(f"✅ Архив создан: {archive_path}")
    except Exception as e:
        print(f"❌ Ошибка при создании архива: {e}")
        return 1
    
    try:
        # Копируем архив на сервер
        print("📤 Копирование архива на сервер...")
        child = pexpect.spawn(f'scp -o StrictHostKeyChecking=no {archive_path} {server}:~/project.tar.gz', encoding='utf-8', timeout=300)
        child.logfile = sys.stdout
        
        index = child.expect(['password:', 'Permission denied', pexpect.EOF, pexpect.TIMEOUT], timeout=30)
        
        if index == 0:
            child.sendline(password)
            child.expect(pexpect.EOF, timeout=300)
        elif index == 1:
            print("❌ Permission denied")
            os.unlink(archive_path)
            return 1
        
        print("✅ Архив скопирован")
        
        # Распаковываем на сервере
        print("📦 Распаковка на сервере...")
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout
        
        index = child.expect(['password:', 'Permission denied', r'\$ ', r'# ', pexpect.EOF, pexpect.TIMEOUT], timeout=10)
        
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)
        elif index == 1:
            print("❌ Permission denied")
            os.unlink(archive_path)
            return 1
        
        # Создаем директорию и распаковываем
        child.sendline(f'sudo mkdir -p {server_path} && sudo chown -R debian:debian {server_path}')
        index = child.expect(['password:', r'\$ ', r'# ', pexpect.TIMEOUT], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline(f'cd {server_path} && tar -xzf ~/project.tar.gz && rm ~/project.tar.gz')
        child.expect([r'\$ ', r'# '], timeout=60)
        
        child.sendline(f'ls -la {server_path} | head -10')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('echo "✅ Файлы скопированы"')
        child.expect([r'\$ ', r'# '], timeout=10)
        
        child.sendline('exit')
        child.expect(pexpect.EOF, timeout=5)
        
        # Удаляем временный архив
        os.unlink(archive_path)
        
        print("\n✅ Проект успешно скопирован на сервер!")
        return 0
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        if os.path.exists(archive_path):
            os.unlink(archive_path)
        return 1

if __name__ == "__main__":
    sys.exit(main())

