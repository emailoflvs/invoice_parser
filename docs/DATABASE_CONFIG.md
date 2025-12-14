# Конфигурация базы данных

## Структура настроек БД

В проекте используется единая система настроек базы данных без дублирования.

### Переменные в .env

#### Для Docker Compose (обязательные):
```env
DB_USER=invoiceparser          # Имя пользователя PostgreSQL
DB_PASSWORD=invoiceparser_password  # Пароль PostgreSQL
DB_NAME=invoiceparser            # Имя базы данных
DB_PORT=5432                   # Порт PostgreSQL
```

Эти переменные используются Docker Compose для настройки контейнера PostgreSQL (маппятся на `POSTGRES_*` внутри контейнера).

#### Для приложения (автоматически):
```env
DATABASE_URL=postgresql+asyncpg://invoiceparser:invoiceparser_password@db:5432/invoiceparser
```

**ВАЖНО**: `DATABASE_URL` автоматически формируется из `DB_*` переменных скриптом `setup_env.py`. Не нужно редактировать его вручную!

### Дополнительные настройки БД:
```env
DB_ECHO=false              # SQLAlchemy query logging
DB_POOL_SIZE=50            # Размер пула соединений
DB_MAX_OVERFLOW=20         # Максимальное количество дополнительных соединений
DB_AUTO_MIGRATE=true       # Автоматический запуск миграций при старте
```

## Как это работает

### 1. Docker Compose использует DB_* (маппятся на POSTGRES_*)
```yaml
services:
  db:
    environment:
      POSTGRES_USER: ${DB_USER:-invoiceparser}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-invoiceparser_password}
      POSTGRES_DB: ${DB_NAME:-invoiceparser}
```

### 2. Приложение использует DATABASE_URL
```python
# В config.py
database_url: str = Field(
    alias="DATABASE_URL",
    default="postgresql+asyncpg://invoiceparser:invoiceparser_password@db:5432/invoiceparser"
)
```

### 3. Автоматическое формирование
Скрипт `setup_env.py` автоматически формирует `DATABASE_URL` из `DB_*` переменных:
```python
DATABASE_URL = f'postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@db:5432/{DB_NAME}'
```

## Миграция с POSTGRES_* на DB_*

Старые переменные `POSTGRES_*` были заменены на `DB_*`:
- ✅ `DB_USER` (было `POSTGRES_USER`)
- ✅ `DB_PASSWORD` (было `POSTGRES_PASSWORD`)
- ✅ `DB_NAME` (было `POSTGRES_DB`)
- ✅ `DB_PORT` (было `POSTGRES_PORT`)

Скрипт `setup_env.py` автоматически мигрирует старые переменные при обновлении `.env`.

## Настройка базы данных

### Автоматическая настройка:
```bash
python3 scripts/setup_env.py
```

Этот скрипт:
1. Читает существующие `POSTGRES_*` переменные
2. Автоматически формирует `DATABASE_URL`
3. Сохраняет все в `.env`

### Ручная настройка:

Если нужно изменить настройки БД:

1. Отредактируйте `DB_*` переменные в `.env`:
   ```env
   DB_USER=myuser
   DB_PASSWORD=mypassword
   DB_NAME=mydatabase
   ```

2. Запустите `setup_env.py` для обновления `DATABASE_URL`:
   ```bash
   docker-compose exec app python scripts/setup_env.py
   ```

3. Перезапустите контейнеры:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

## Проверка конфигурации

Проверить текущие настройки:
```bash
# Показать настройки БД из .env
docker-compose exec app grep -E "DB_|DATABASE" /app/.env | grep -v "^#"

# Проверить подключение
docker-compose exec app python -c "
from invoiceparser.core.config import Config
config = Config.load()
print(f'Database URL: {config.database_url}')
"
```

## Миграции

Миграции Alembic используют `DATABASE_URL` из конфигурации:
- Автоматически запускаются при старте (если `DB_AUTO_MIGRATE=true`)
- Или вручную: `docker-compose exec app python -m alembic upgrade head`

## Резюме

- ✅ **DB_*** - для Docker Compose (источник истины, маппятся на POSTGRES_* внутри контейнера)
- ✅ **DATABASE_URL** - для приложения (автоматически формируется из DB_*)
- ❌ **POSTGRES_*** - заменены на DB_* (старые переменные)

Нет дублирования - все настройки БД в одном месте!

