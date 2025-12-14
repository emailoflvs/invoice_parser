# Авторизация по паролю

Система авторизации реализована с использованием JWT токенов и хеширования паролей через bcrypt.

## Быстрый старт с Docker Compose

### 1. Настройка окружения

Скопируйте `.env.example` в `.env` и настройте параметры:

```bash
cp .env.example .env
```

**Важно**: Измените `JWT_SECRET_KEY` на длинный случайный ключ для продакшена!

```env
JWT_SECRET_KEY=your-very-long-random-secret-key-here-change-this-in-production
```

### 2. Запуск через Docker Compose

```bash
# Сборка и запуск
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f app
```

Миграции базы данных запускаются автоматически при старте приложения.

### 3. Создание первого пользователя

После запуска приложения создайте первого пользователя:

```bash
# Создать пользователя (работает только в контейнере)
docker-compose exec app python scripts/create_user.py admin your_password admin@example.com --superuser
```

## API Эндпоинты

### Регистрация нового пользователя

```bash
POST /api/auth/register
Content-Type: application/json

{
  "username": "user1",
  "password": "secure_password",
  "email": "user1@example.com"
}
```

### Вход в систему

```bash
POST /api/auth/login
Content-Type: application/json

{
  "username": "user1",
  "password": "secure_password"
}
```

Ответ:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "user1"
}
```

### Получение информации о текущем пользователе

```bash
GET /api/auth/me
Authorization: Bearer <your_jwt_token>
```

### Использование токена в запросах

Все защищенные эндпоинты требуют JWT токен в заголовке:

```bash
Authorization: Bearer <your_jwt_token>
```

Защищенные эндпоинты:
- `POST /parse` - парсинг документов
- `POST /save` - сохранение данных
- `GET /api/search/documents` - поиск документов

## Настройки JWT

В файле `.env` можно настроить:

- `JWT_SECRET_KEY` - секретный ключ для подписи токенов (обязательно измените!)
- `JWT_ALGORITHM` - алгоритм подписи (по умолчанию HS256)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - время жизни токена в минутах (по умолчанию 43200 = 30 дней)

## Безопасность

1. **Всегда используйте сильный JWT_SECRET_KEY** в продакшене
2. **Используйте HTTPS** для передачи токенов
3. **Регулярно обновляйте пароли** пользователей
4. **Не храните токены** в localStorage в продакшене (используйте httpOnly cookies)

## Управление пользователями

### Создание пользователя через скрипт (в Docker контейнере)

```bash
docker-compose exec app python scripts/create_user.py <username> <password> [email] [--superuser]
```

Примеры:
```bash
# Обычный пользователь
docker-compose exec app python scripts/create_user.py user1 password123 user1@example.com

# Суперпользователь
docker-compose exec app python scripts/create_user.py admin admin123 admin@example.com --superuser
```

### Создание пользователя через API

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "securepass",
    "email": "newuser@example.com"
  }'
```

## Миграции базы данных

Миграции запускаются автоматически при старте приложения (если `DB_AUTO_MIGRATE=true`).

Для ручного запуска:

```bash
docker-compose exec app python -m alembic upgrade head
```

## Troubleshooting

### Проблема: "Could not validate credentials"

- Проверьте, что токен не истек
- Убедитесь, что используете правильный формат: `Bearer <token>`
- Проверьте, что `JWT_SECRET_KEY` совпадает в конфигурации

### Проблема: "User already exists"

Пользователь с таким username или email уже существует. Используйте другой username/email.

### Проблема: Миграции не запускаются

Проверьте логи:
```bash
docker-compose logs app | grep -i migration
```

Убедитесь, что база данных доступна и `DB_AUTO_MIGRATE=true` в `.env`.

Запуск миграций вручную (в контейнере):
```bash
docker-compose exec app python -m alembic upgrade head
```

