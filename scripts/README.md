# Скрипты для работы в Docker контейнере

Все скрипты предназначены для запуска **только внутри Docker контейнера**.

## Доступные скрипты

### 1. `wait_for_db.py`
Ожидание готовности базы данных.

**Использование:**
```bash
docker-compose exec app python scripts/wait_for_db.py
```

### 2. `create_user.py`
Создание нового пользователя в базе данных.

**Использование:**
```bash
# Обычный пользователь
docker-compose exec app python scripts/create_user.py username password email@example.com

# Суперпользователь
docker-compose exec app python scripts/create_user.py admin admin123 admin@example.com --superuser
```

### 3. `generate_jwt_secret.py`
Генерация безопасного JWT секретного ключа.

**Использование:**
```bash
docker-compose exec app python scripts/generate_jwt_secret.py
```

### 4. `setup_env.py`
Настройка .env файла (запускается автоматически при старте).

**Использование:**
```bash
docker-compose exec app python scripts/setup_env.py
```

**Примечание:** Этот скрипт обычно не нужно запускать вручную, так как .env файл настраивается автоматически.

### 5. `cleanup_env.py`
Очистка .env файла от дублирующихся переменных.

**Использование:**
```bash
docker-compose exec app python scripts/cleanup_env.py
```

## Важно

⚠️ **Все скрипты должны запускаться через `docker-compose exec app`**

Не запускайте скрипты локально, так как:
- Они требуют доступа к базе данных внутри Docker сети
- Они используют пути, специфичные для контейнера (`/app/src`, `/app/.env`)
- Они требуют всех зависимостей, установленных в контейнере

## Примеры использования

### Создание первого пользователя:
```bash
docker-compose exec app python scripts/create_user.py admin admin123 admin@example.com --superuser
```

### Генерация JWT ключа:
```bash
docker-compose exec app python scripts/generate_jwt_secret.py
```

### Проверка готовности БД:
```bash
docker-compose exec app python scripts/wait_for_db.py
```

## Пути в контейнере

Все скрипты автоматически определяют, работают ли они в контейнере:
- В контейнере: `/app/src`, `/app/.env`
- Локально (для разработки): относительные пути от корня проекта

Но рекомендуется использовать **только в контейнере** для консистентности.










