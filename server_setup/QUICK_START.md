# Быстрый старт: Настройка сервера

## Шаг 1: Подключение к серверу

```bash
ssh debian@57.129.62.58
# Пароль: Polik350
```

## Шаг 2: Проверка сервера

После подключения выполните быструю проверку:

```bash
# Проверка системы
uname -a
df -h
free -h

# Проверка Docker
docker --version 2>/dev/null || echo "Docker не установлен"
docker-compose --version 2>/dev/null || echo "Docker Compose не установлен"
```

## Шаг 3: Настройка (если Docker не установлен)

### Вариант A: Автоматическая настройка

1. Скопируйте скрипт `setup_server.sh` на сервер
2. Выполните: `sudo bash setup_server.sh`

### Вариант B: Ручная установка Docker

```bash
# Обновление
sudo apt-get update && sudo apt-get upgrade -y

# Установка Docker (см. подробную инструкцию в README.md)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Добавление пользователя в группу docker
sudo usermod -aG docker debian
newgrp docker  # или выйдите и войдите снова

# Проверка
docker run hello-world
```

## Шаг 4: Развертывание проекта

### С локальной машины:

```bash
cd /home/lvs/Desktop/AI/servers/invoice_parser/server_setup
./deploy_to_server.sh
```

### Или вручную:

```bash
# Создание директории на сервере
ssh debian@57.129.62.58 "sudo mkdir -p /opt/docker-projects/invoice_parser && sudo chown -R debian:debian /opt/docker-projects/invoice_parser"

# Копирование файлов
rsync -avz --exclude 'venv' --exclude '__pycache__' \
  /home/lvs/Desktop/AI/servers/invoice_parser/ \
  debian@57.129.62.58:/opt/docker-projects/invoice_parser/
```

### На сервере:

```bash
cd /opt/docker-projects/invoice_parser

# Создание .env (если нужно)
nano .env

# Запуск
docker compose up -d --build

# Проверка
docker compose ps
docker compose logs -f
```

## Полезные команды

```bash
# Статус контейнеров
docker compose ps

# Логи
docker compose logs -f

# Остановка
docker compose down

# Перезапуск
docker compose restart

# Обновление после изменений
docker compose up -d --build
```

## Что дальше?

См. подробную инструкцию в `README.md`

