#!/bin/bash
# Скрипт для проверки состояния сервера
# Выполнять на сервере после подключения

echo "🔍 Проверка состояния сервера..."
echo ""

echo "📊 Системная информация:"
echo "OS: $(uname -a)"
echo "Uptime: $(uptime)"
echo ""

echo "💾 Дисковое пространство:"
df -h | grep -E '^/dev/|Filesystem'
echo ""

echo "🧠 Использование памяти:"
free -h
echo ""

echo "🐳 Docker:"
if command -v docker &> /dev/null; then
    echo "  Docker версия: $(docker --version)"
    echo "  Docker статус: $(systemctl is-active docker)"
    docker info --format "  Контейнеры: {{.ContainersRunning}} запущено, {{.ContainersStopped}} остановлено"
    echo "  Образы: $(docker images -q | wc -l) образов"
    echo "  Volumes: $(docker volume ls -q | wc -l) volumes"
    echo "  Networks: $(docker network ls -q | wc -l) сетей"
else
    echo "  ❌ Docker не установлен"
fi
echo ""

echo "🐳 Docker Compose:"
if command -v docker-compose &> /dev/null; then
    echo "  Docker Compose (standalone): $(docker-compose --version)"
elif docker compose version &> /dev/null 2>&1; then
    echo "  Docker Compose (plugin): $(docker compose version)"
else
    echo "  ❌ Docker Compose не установлен"
fi
echo ""

echo "📁 Структура проектов:"
if [ -d "/opt/docker-projects" ]; then
    echo "  Директория проектов: /opt/docker-projects"
    echo "  Проекты:"
    ls -1 /opt/docker-projects 2>/dev/null | grep -v "^shared$\|^backups$" | sed 's/^/    - /' || echo "    (нет проектов)"
else
    echo "  ❌ Директория /opt/docker-projects не найдена"
fi
echo ""

echo "🔥 Firewall:"
if command -v ufw &> /dev/null; then
    echo "  Статус: $(ufw status | head -1)"
    ufw status numbered 2>/dev/null | tail -n +4 | sed 's/^/    /'
else
    echo "  ❌ UFW не установлен"
fi
echo ""

echo "🌐 Сетевые подключения:"
echo "  Открытые порты:"
netstat -tuln 2>/dev/null | grep LISTEN | awk '{print "    " $4}' | sort -u || ss -tuln 2>/dev/null | grep LISTEN | awk '{print "    " $4}' | sort -u
echo ""

echo "👤 Пользователи:"
echo "  Текущий пользователь: $(whoami)"
echo "  Группы: $(groups)"
echo "  В группе docker: $(groups | grep -q docker && echo 'да' || echo 'нет')"
echo ""

echo "✅ Проверка завершена"









