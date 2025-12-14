# Настройка и запуск через Docker Compose

## Быстрый старт

### 1. Настройка окружения

Создайте файл `.env` из примера:

```bash
cp .env.example .env
```

**ВАЖНО**: Отредактируйте `.env` и установите:
- `JWT_SECRET_KEY` - длинный случайный ключ для JWT токенов
- `GEMINI_API_KEY` - ваш API ключ от Google Gemini
- Другие настройки по необходимости

### 2. Запуск

```bash
# Простой способ
./docker-start.sh

# Или вручную
docker-compose up -d --build
```

### 3. Создание первого пользователя

После запуска создайте первого пользователя:

```bash
docker-compose exec app python scripts/create_user.py admin your_password admin@example.com --superuser
```

### 4. Проверка работы

- Веб-интерфейс: http://localhost:8000
- API документация: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Полезные команды

### Просмотр логов

```bash
# Все логи
docker-compose logs -f

# Только приложение
docker-compose logs -f app

# Только база данных
docker-compose logs -f db
```

### Остановка

```bash
docker-compose down
```

### Перезапуск

```bash
docker-compose restart app
```

### Выполнение команд в контейнере

**ВАЖНО:** Все команды должны выполняться через `docker-compose exec app`

```bash
# Создать пользователя
docker-compose exec app python scripts/create_user.py username password email@example.com

# Запустить миграции вручную
docker-compose exec app python -m alembic upgrade head

# Генерация JWT ключа
docker-compose exec app python scripts/generate_jwt_secret.py

# Войти в контейнер (для отладки)
docker-compose exec app bash
```

### Очистка данных

```bash
# Остановить и удалить контейнеры и volumes
docker-compose down -v

# Удалить только volumes (данные БД)
docker volume rm invoice_parser_postgres_data
```

## Структура сервисов

- **db** - PostgreSQL база данных
- **app** - Основное приложение (Web API)
- **telegram-bot** - Telegram бот (опционально, профиль `telegram`)
- **email-poller** - Email поллер (опционально, профиль `email`)

## Запуск опциональных сервисов

### Telegram бот

```bash
docker-compose --profile telegram up -d telegram-bot
```

### Email поллер

```bash
docker-compose --profile email up -d email-poller
```

## Автоматические миграции

Миграции базы данных запускаются автоматически при старте приложения.

Если нужно запустить миграции вручную:

```bash
docker-compose exec app python -m alembic upgrade head
```

## Troubleshooting

### Проблема: "Database is not ready"

База данных еще не готова. Подождите несколько секунд и проверьте логи:

```bash
docker-compose logs db
```

### Проблема: "Migration failed"

Проверьте подключение к базе данных и логи:

```bash
docker-compose logs app | grep -i migration
```

### Проблема: "Port 8000 already in use"

Измените порт в `.env`:

```env
WEB_PORT=8001
```

И обновите `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"
```

### Проблема: "JWT_SECRET_KEY not set"

Установите `JWT_SECRET_KEY` в `.env` файле:

```env
JWT_SECRET_KEY=your-very-long-random-secret-key-here
```

## Production настройки

Для продакшена:

1. **Измените все пароли и секретные ключи** в `.env`
2. **Используйте HTTPS** (настройте reverse proxy, например nginx)
3. **Не монтируйте `src/` как volume** - пересоберите образ:
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```
4. **Настройте резервное копирование** базы данных
5. **Используйте переменные окружения** вместо `.env` файла для секретов

