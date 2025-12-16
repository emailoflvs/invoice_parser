# Настройка сервера для работы с Docker-контейнерами

Этот набор скриптов поможет настроить новый сервер Debian для работы с несколькими Docker-приложениями, каждое со своей БД.

## Шаг 1: Подключение к серверу

```bash
ssh debian@57.129.62.58
# Пароль: Polik350
```

## Шаг 2: Проверка текущего состояния

После подключения выполните проверку сервера:

```bash
# Скопируйте скрипт на сервер или создайте его вручную
cat > check_server.sh << 'EOF'
# [содержимое check_server.sh]
EOF

chmod +x check_server.sh
./check_server.sh
```

Или выполните команды вручную:

```bash
uname -a
docker --version 2>/dev/null || echo "Docker не установлен"
docker-compose --version 2>/dev/null || echo "Docker Compose не установлен"
df -h
free -h
ls -la /
systemctl status docker 2>/dev/null || echo "Docker service не запущен"
```

## Шаг 3: Настройка сервера

### Вариант A: Автоматическая настройка (рекомендуется)

```bash
# Скопируйте скрипт setup_server.sh на сервер
# Затем выполните:
sudo bash setup_server.sh
```

### Вариант B: Ручная настройка

Если нужно настроить вручную, выполните следующие команды:

#### 3.1. Обновление системы

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

#### 3.2. Установка Docker

```bash
# Удаление старых версий (если есть)
sudo apt-get remove -y docker docker-engine docker.io containerd runc

# Установка зависимостей
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Добавление официального GPG ключа Docker
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Добавление репозитория Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Запуск Docker
sudo systemctl enable docker
sudo systemctl start docker

# Добавление пользователя в группу docker (чтобы не использовать sudo)
sudo usermod -aG docker debian
```

**Важно:** После добавления в группу docker нужно выйти и войти снова, или выполнить:
```bash
newgrp docker
```

#### 3.3. Проверка установки Docker

```bash
docker --version
docker compose version
docker run hello-world
```

#### 3.4. Настройка firewall

```bash
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
```

#### 3.5. Создание структуры директорий

```bash
sudo mkdir -p /opt/docker-projects
sudo mkdir -p /opt/docker-projects/shared
sudo mkdir -p /opt/docker-projects/backups
sudo chown -R debian:debian /opt/docker-projects
```

## Шаг 4: Развертывание проекта invoice_parser

### 4.1. Создание директории проекта

```bash
mkdir -p /opt/docker-projects/invoice_parser
cd /opt/docker-projects/invoice_parser
```

### 4.2. Копирование файлов проекта

С локальной машины:

```bash
# Установите sshpass для удобства (опционально)
sudo apt-get install -y sshpass

# Копирование файлов на сервер
rsync -avz --exclude 'venv' --exclude '__pycache__' --exclude '*.pyc' \
  /home/lvs/Desktop/AI/servers/invoice_parser/ \
  debian@57.129.62.58:/opt/docker-projects/invoice_parser/
```

Или используйте scp:

```bash
scp -r /home/lvs/Desktop/AI/servers/invoice_parser/* \
  debian@57.129.62.58:/opt/docker-projects/invoice_parser/
```

### 4.3. Настройка окружения

На сервере:

```bash
cd /opt/docker-projects/invoice_parser

# Создание .env файла (если его нет)
if [ ! -f .env ]; then
    cp .env.example .env 2>/dev/null || touch .env
    # Отредактируйте .env файл с нужными настройками
    nano .env
fi

# Убедитесь, что порты не конфликтуют с другими проектами
# В .env файле можно изменить:
# APP_PORT=8000 (или другой свободный порт)
# DB_EXTERNAL_PORT=5433 (или другой свободный порт)
```

### 4.4. Запуск проекта

```bash
cd /opt/docker-projects/invoice_parser

# Сборка и запуск
docker compose up -d --build

# Просмотр логов
docker compose logs -f

# Проверка статуса
docker compose ps
```

## Управление несколькими проектами

### Структура директорий

```
/opt/docker-projects/
├── invoice_parser/          # Проект 1
│   ├── docker-compose.yml
│   ├── .env
│   └── ...
├── another_project/          # Проект 2
│   ├── docker-compose.yml
│   └── ...
├── shared/                   # Общие ресурсы
└── backups/                  # Резервные копии
```

### Изоляция проектов

Каждый проект должен:
- Использовать уникальные имена контейнеров (через `container_name` в docker-compose.yml)
- Использовать уникальные имена сетей (через `networks` в docker-compose.yml)
- Использовать уникальные имена volumes (через `volumes` в docker-compose.yml)
- Использовать разные внешние порты (через переменные окружения в .env)

### Полезные команды

```bash
# Список всех контейнеров
docker ps -a

# Список всех сетей
docker network ls

# Список всех volumes
docker volume ls

# Логи конкретного проекта
cd /opt/docker-projects/invoice_parser
docker compose logs -f

# Остановка проекта
docker compose down

# Остановка с удалением volumes (ОСТОРОЖНО!)
docker compose down -v

# Перезапуск проекта
docker compose restart

# Обновление проекта (после изменений в коде)
docker compose up -d --build
```

## Мониторинг и обслуживание

### Проверка использования ресурсов

```bash
# Использование диска
df -h
docker system df

# Использование памяти и CPU
htop
docker stats

# Логи системы
journalctl -u docker -f
```

### Резервное копирование

```bash
# Бэкап БД проекта
cd /opt/docker-projects/invoice_parser
docker compose exec db pg_dump -U invoiceparser invoiceparser > \
  /opt/docker-projects/backups/invoice_parser_$(date +%Y%m%d_%H%M%S).sql

# Бэкап volumes
docker run --rm -v invoiceparser_postgres_data:/data -v /opt/docker-projects/backups:/backup \
  alpine tar czf /backup/invoice_parser_data_$(date +%Y%m%d_%H%M%S).tar.gz /data
```

## Безопасность

1. **SSH ключи:** Настройте SSH-ключи вместо паролей
2. **Firewall:** Убедитесь, что открыты только необходимые порты
3. **Обновления:** Регулярно обновляйте систему и Docker
4. **Пароли:** Используйте сильные пароли в .env файлах
5. **Бэкапы:** Регулярно делайте резервные копии

## Решение проблем

### Docker не запускается

```bash
sudo systemctl status docker
sudo journalctl -u docker -n 50
```

### Проблемы с правами

```bash
# Убедитесь, что пользователь в группе docker
groups
# Если нет, добавьте:
sudo usermod -aG docker debian
newgrp docker
```

### Конфликты портов

```bash
# Проверка занятых портов
sudo netstat -tuln | grep LISTEN
# или
sudo ss -tuln | grep LISTEN
```

## Следующие шаги

После настройки сервера:

1. ✅ Настройте SSH-ключи для безопасного доступа
2. ✅ Настройте мониторинг (опционально: Prometheus, Grafana)
3. ✅ Настройте автоматические бэкапы
4. ✅ Настройте домен и SSL-сертификаты (Let's Encrypt)
5. ✅ Настройте reverse proxy (Nginx/Traefik) для нескольких проектов

