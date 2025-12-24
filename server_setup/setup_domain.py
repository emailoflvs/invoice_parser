#!/usr/bin/env python3
"""Настройка домена doclogic.eu на сервере"""
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
    domain = "doclogic.eu"

    try:
        pexpect = install_pexpect()
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return 1

    print("🌐 Настройка домена doclogic.eu...\n")

    try:
        child = pexpect.spawn(f'ssh -o StrictHostKeyChecking=no {server}', encoding='utf-8', timeout=30)
        child.logfile = sys.stdout

        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=15)

        print("\n" + "="*60)
        print("1️⃣  УСТАНОВКА NGINX")
        print("="*60)
        child.sendline('sudo apt-get update')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=30)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=30)

        child.sendline('sudo apt-get install -y nginx certbot python3-certbot-nginx')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=60)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=60)

        print("\n" + "="*60)
        print("2️⃣  СОЗДАНИЕ КОНФИГУРАЦИИ NGINX")
        print("="*60)

        nginx_config = f"""server {{
    listen 80;
    server_name {domain} www.{domain};

    location / {{
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }}
}}
"""

        child.sendline(f'echo \'{nginx_config}\' | sudo tee /etc/nginx/sites-available/{domain}')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline(f'sudo ln -sf /etc/nginx/sites-available/{domain} /etc/nginx/sites-enabled/')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('sudo rm -f /etc/nginx/sites-enabled/default')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("3️⃣  ПРОВЕРКА КОНФИГУРАЦИИ NGINX")
        print("="*60)
        child.sendline('sudo nginx -t')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("4️⃣  ПЕРЕЗАПУСК NGINX")
        print("="*60)
        child.sendline('sudo systemctl restart nginx')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('sudo systemctl enable nginx')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("5️⃣  ПРОВЕРКА СТАТУСА NGINX")
        print("="*60)
        child.sendline('sudo systemctl status nginx --no-pager | head -10')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("6️⃣  ОТКРЫТИЕ ПОРТОВ В FIREWALL")
        print("="*60)
        child.sendline('sudo ufw allow 80/tcp')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('sudo ufw allow 443/tcp')
        index = child.expect(['password:', r'\$ ', r'# '], timeout=10)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# '], timeout=10)

        child.sendline('sudo ufw status | grep -E "80|443"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("7️⃣  ПРОВЕРКА ДОСТУПНОСТИ")
        print("="*60)
        child.sendline(f'curl -s -o /dev/null -w "HTTP Status: %{{http_code}}\n" http://localhost/ -H "Host: {domain}"')
        child.expect([r'\$ ', r'# '], timeout=10)

        print("\n" + "="*60)
        print("8️⃣  НАСТРОЙКА SSL (Let's Encrypt)")
        print("="*60)
        print("⚠️  ВАЖНО: Перед настройкой SSL убедитесь, что:")
        print("   - DNS записи для домена указывают на IP сервера (57.129.62.58)")
        print("   - Домен доступен по HTTP (порт 80)")
        print("\nДля настройки SSL выполните:")
        print(f"   sudo certbot --nginx -d {domain} -d www.{domain}")
        print("\nИли автоматически (если DNS уже настроен):")
        child.sendline(f'sudo certbot --nginx -d {domain} -d www.{domain} --non-interactive --agree-tos --email admin@{domain} --redirect')
        index = child.expect(['password:', r'\$ ', r'# ', 'Error', 'Failed'], timeout=120)
        if index == 0:
            child.sendline(password)
            child.expect([r'\$ ', r'# ', 'Error', 'Failed'], timeout=120)

        print("\n" + "="*60)
        print("✅ НАСТРОЙКА ЗАВЕРШЕНА")
        print("="*60)
        print(f"\n🌐 Проверьте домен:")
        print(f"   http://{domain}")
        print(f"   http://www.{domain}")
        print(f"\n📋 Полезные команды:")
        print(f"   sudo nginx -t              # Проверка конфигурации")
        print(f"   sudo systemctl status nginx # Статус nginx")
        print(f"   sudo certbot renew         # Обновление SSL сертификата")
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










