#!/bin/bash
# Скрипт для первоначальной настройки сервера
# Выполнять от имени root или с sudo

set -e

echo "🚀 Начинаем настройку сервера для работы с Docker-контейнерами..."

# Обновление системы
echo "📦 Обновление системы..."
apt-get update
apt-get upgrade -y

# Установка необходимых пакетов
echo "📦 Установка базовых пакетов..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    net-tools \
    ufw \
    fail2ban \
    unattended-upgrades \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release

# Установка Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Установка Docker..."
    # Удаляем старые версии
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

    # Добавляем официальный GPG ключ Docker
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    # Добавляем репозиторий Docker
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Устанавливаем Docker
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    # Запускаем Docker
    systemctl enable docker
    systemctl start docker

    # Добавляем пользователя debian в группу docker (чтобы не использовать sudo)
    usermod -aG docker debian

    echo "✅ Docker установлен"
else
    echo "✅ Docker уже установлен: $(docker --version)"
fi

# Установка Docker Compose (standalone, если не установлен через plugin)
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "🐳 Установка Docker Compose (standalone)..."
    DOCKER_COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep 'tag_name' | cut -d\" -f4)
    curl -L "https://github.com/docker/compose/releases/download/${DOCKER_COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "✅ Docker Compose установлен"
else
    echo "✅ Docker Compose уже установлен"
fi

# Настройка firewall
echo "🔥 Настройка firewall..."
ufw --force enable
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp   # SSH
ufw allow 80/tcp   # HTTP
ufw allow 443/tcp  # HTTPS
# Порты для приложений будут открываться по мере необходимости

# Настройка автоматических обновлений безопасности
echo "🔒 Настройка автоматических обновлений..."
echo 'Unattended-Upgrade::Automatic-Reboot "false";' >> /etc/apt/apt.conf.d/50unattended-upgrades
echo 'Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";' >> /etc/apt/apt.conf.d/50unattended-upgrades

# Создание структуры директорий для проектов
echo "📁 Создание структуры директорий..."
mkdir -p /opt/docker-projects
mkdir -p /opt/docker-projects/shared
mkdir -p /opt/docker-projects/backups
chown -R debian:debian /opt/docker-projects

# Создание скрипта для управления проектами
cat > /usr/local/bin/docker-project << 'EOF'
#!/bin/bash
# Утилита для управления Docker-проектами
# Использование: docker-project <command> <project_name>

PROJECTS_DIR="/opt/docker-projects"

case "$1" in
    list)
        echo "📦 Список проектов:"
        ls -1 "$PROJECTS_DIR" | grep -v "^shared$\|^backups$"
        ;;
    create)
        if [ -z "$2" ]; then
            echo "❌ Укажите имя проекта: docker-project create <project_name>"
            exit 1
        fi
        mkdir -p "$PROJECTS_DIR/$2"
        echo "✅ Проект $2 создан в $PROJECTS_DIR/$2"
        ;;
    remove)
        if [ -z "$2" ]; then
            echo "❌ Укажите имя проекта: docker-project remove <project_name>"
            exit 1
        fi
        read -p "Вы уверены, что хотите удалить проект $2? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$PROJECTS_DIR/$2"
            echo "✅ Проект $2 удален"
        fi
        ;;
    *)
        echo "Использование: docker-project {list|create|remove} [project_name]"
        exit 1
        ;;
esac
EOF

chmod +x /usr/local/bin/docker-project

echo ""
echo "✅ Настройка сервера завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Выйдите и войдите снова (или выполните: newgrp docker) для применения прав группы docker"
echo "2. Проверьте установку: docker --version && docker compose version"
echo "3. Создайте проект: docker-project create invoice_parser"
echo "4. Скопируйте файлы проекта в /opt/docker-projects/invoice_parser"
echo ""
echo "💡 Полезные команды:"
echo "   - docker-project list          # Список проектов"
echo "   - docker-project create <name> # Создать проект"
echo "   - docker ps                    # Список контейнеров"
echo "   - docker network ls            # Список сетей"
echo "   - docker volume ls             # Список volumes"










