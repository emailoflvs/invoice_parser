# Docker Быстрый старт

## Что было исправлено

### 1. Автоматическая установка зависимостей ✅
Все Python зависимости теперь устанавливаются автоматически при сборке Docker образа (строка 18 в Dockerfile).

### 2. Фронтенд теперь работает ✅
- Добавлено копирование статических файлов (папка `static/`) в Docker контейнер
- Исправлены ошибки инициализации логирования во всех точках входа (`main_web.py`, `main_telegram.py`, `main_email.py`)

## Как запустить проект

### Первый запуск

1. **Создайте файл `.env`** (если еще не создан):
```bash
cp env.example .env
```

2. **Отредактируйте `.env` файл**:
   - Обязательно укажите `GEMINI_API_KEY` (ваш API ключ от Google Gemini)
   - Обязательно измените `WEB_AUTH_TOKEN` на свой секретный токен

3. **Запустите контейнер**:
```bash
docker-compose up --build -d
```

4. **Откройте браузер**: http://localhost:8000

5. **Настройте токен авторизации**:
   - Нажмите на иконку настроек ⚙️ (правый нижний угол)
   - Введите ваш `WEB_AUTH_TOKEN` из `.env` файла

### Остановка контейнера

```bash
docker-compose down
```

### Перезапуск после изменений в коде

```bash
docker-compose down
docker-compose up --build -d
```

### Просмотр логов

```bash
# Все логи
docker-compose logs app

# Последние 50 строк
docker-compose logs --tail 50 app

# Следить за логами в реальном времени
docker-compose logs -f app
```

### Проверка статуса

```bash
docker-compose ps
```

## Дополнительные сервисы

### Telegram бот (опционально)

```bash
docker-compose --profile telegram up -d
```

### Email поллер (опционально)

```bash
docker-compose --profile email up -d
```

### Запуск всех сервисов

```bash
docker-compose --profile telegram --profile email up -d
```

## Структура Docker контейнера

- **Базовый образ**: Python 3.11-slim
- **Системные зависимости**: poppler-utils, libgl1, libglib2.0-0
- **Python зависимости**: автоматически из `requirements.txt`
- **Монтированные тома**:
  - `./invoices` → `/app/invoices` (загруженные документы)
  - `./output` → `/app/output` (результаты обработки)
  - `./logs` → `/app/logs` (логи приложения)
  - `./.env` → `/app/.env` (конфигурация)

## Устранение проблем

### Контейнер не запускается

```bash
# Полная очистка
docker-compose down --rmi all --volumes

# Пересборка и запуск
docker-compose up --build -d
```

### Фронтенд не загружается

1. Убедитесь что контейнер запущен: `docker-compose ps`
2. Проверьте логи: `docker-compose logs app`
3. Проверьте порт 8000 не занят другим процессом: `sudo lsof -i :8000`

### Ошибка авторизации

Убедитесь, что:
1. `WEB_AUTH_TOKEN` указан в `.env` файле
2. Вы ввели правильный токен в настройках фронтенда (⚙️ иконка)

## Полезные команды

```bash
# Войти в контейнер
docker-compose exec app bash

# Проверить версию Python
docker-compose exec app python --version

# Проверить установленные пакеты
docker-compose exec app pip list

# Проверить файловую структуру
docker-compose exec app ls -la /app/
```

