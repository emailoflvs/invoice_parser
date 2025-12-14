# Работа только в Docker контейнере

## ⚠️ ВАЖНО: Программа работает только в Docker контейнере

Все команды и скрипты должны выполняться **только через Docker**.

## Почему только Docker?

1. **База данных** доступна только внутри Docker сети
2. **Зависимости** установлены только в контейнере
3. **Пути** настроены для контейнера (`/app/src`, `/app/.env`)
4. **Консистентность** - одинаковое окружение для всех

## Все команды через Docker

### ✅ Правильно (в контейнере):
```bash
# Создание пользователя
docker-compose exec app python scripts/create_user.py admin admin123 admin@example.com

# Генерация JWT ключа
docker-compose exec app python scripts/generate_jwt_secret.py

# Запуск миграций
docker-compose exec app python -m alembic upgrade head

# Проверка БД
docker-compose exec db psql -U invoiceparser -d invoiceparser -c "SELECT * FROM users;"
```

### ❌ Неправильно (локально):
```bash
# НЕ РАБОТАЕТ - нет доступа к БД
python scripts/create_user.py admin admin123

# НЕ РАБОТАЕТ - нет зависимостей
python -m alembic upgrade head
```

## Структура путей в контейнере

В Docker контейнере все находится в `/app/`:

```
/app/
├── .env              # Файл конфигурации
├── src/              # Исходный код
│   └── invoiceparser/
├── scripts/          # Скрипты
│   ├── create_user.py
│   ├── generate_jwt_secret.py
│   └── ...
├── alembic/          # Миграции
└── ...
```

## Скрипты автоматически определяют окружение

Все скрипты проверяют, работают ли они в контейнере:

```python
# Автоматическое определение
if Path('/app/.env').exists():
    # В контейнере
    env_path = Path('/app/.env')
else:
    # Локально (не рекомендуется)
    env_path = project_root / '.env'
```

Но **используйте только Docker** для гарантированной работы!

## Быстрый старт

```bash
# 1. Запуск
docker-compose up -d --build

# 2. Создание пользователя
docker-compose exec app python scripts/create_user.py admin admin123 admin@example.com --superuser

# 3. Проверка
docker-compose exec app python -c "
import requests
r = requests.post('http://localhost:8000/api/auth/login',
                  json={'username':'admin','password':'admin123'})
print('Token:', r.json().get('access_token', '')[:50])
"
```

## Проверка работы

```bash
# Health check
docker-compose exec app python -c "
import requests
r = requests.get('http://localhost:8000/health')
print(r.json())
"

# Проверка БД
docker-compose exec db psql -U invoiceparser -d invoiceparser -c "SELECT COUNT(*) FROM users;"
```

## Резюме

- ✅ Все команды через `docker-compose exec app`
- ✅ Все скрипты работают только в контейнере
- ✅ База данных доступна только в Docker сети
- ❌ Не запускайте скрипты локально

**Программа работает только в Docker контейнере!**

