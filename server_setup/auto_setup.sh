#!/usr/bin/expect -f
# Автоматическая настройка сервера через SSH

set timeout 300
set server "debian@57.129.62.58"
set password "Polik350"

# Функция для выполнения команды
proc run_command {cmd} {
    global server password
    spawn ssh -o StrictHostKeyChecking=no $server $cmd
    expect {
        "password:" {
            send "$password\r"
            expect {
                "$ " { return }
                "# " { return }
                timeout { puts "Timeout waiting for prompt"; return }
            }
        }
        "Permission denied" {
            puts "Permission denied"
            return
        }
        timeout {
            puts "Connection timeout"
            return
        }
    }
}

puts "🚀 Начинаю автоматическую настройку сервера..."

# Подключение и проверка
spawn ssh -o StrictHostKeyChecking=no $server
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    timeout {
        puts "Connection timeout"
        exit 1
    }
}

puts "✅ Подключен к серверу"

# Проверка системы
send "echo '=== Системная информация ==='\r"
expect "$ "
send "uname -a\r"
expect "$ "
send "df -h | head -5\r"
expect "$ "
send "free -h\r"
expect "$ "

# Проверка Docker
send "echo '=== Проверка Docker ==='\r"
expect "$ "
send "docker --version 2>/dev/null || echo 'Docker не установлен'\r"
expect "$ "
send "docker-compose --version 2>/dev/null || echo 'Docker Compose не установлен'\r"
expect "$ "

# Если Docker не установлен, устанавливаем
send "if ! command -v docker &> /dev/null; then echo 'Устанавливаю Docker...'; curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh; fi\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}

# Добавление пользователя в группу docker
send "sudo usermod -aG docker debian 2>/dev/null || true\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}

# Создание структуры директорий
send "echo '=== Создание структуры директорий ==='\r"
expect "$ "
send "sudo mkdir -p /opt/docker-projects/invoice_parser\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}
send "sudo chown -R debian:debian /opt/docker-projects\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}

# Настройка firewall
send "echo '=== Настройка firewall ==='\r"
expect "$ "
send "sudo ufw --force enable 2>/dev/null || true\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}
send "sudo ufw allow 22/tcp\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}
send "sudo ufw allow 80/tcp\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}
send "sudo ufw allow 443/tcp\r"
expect {
    "password:" {
        send "$password\r"
        expect "$ "
    }
    "$ " {}
}

send "echo '✅ Базовая настройка завершена'\r"
expect "$ "
send "exit\r"
expect eof

puts "\n✅ Настройка сервера завершена!"
puts "Теперь копирую файлы проекта..."










