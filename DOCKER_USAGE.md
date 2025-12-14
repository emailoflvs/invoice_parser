# Использование Invoice Parser из Docker

Все команды должны запускаться из Docker контейнера.

## Быстрый старт

### 1. Парсинг документа

```bash
# Используя скрипт
./docker-parse.sh invoices/invoice.jpg

# Или напрямую через docker-compose
docker-compose exec app python -m invoiceparser.app.main_cli parse --path /app/invoices/invoice.jpg
```

### 2. Подтверждение данных и экспорт

После парсинга вы получите JSON файл в папке `output/`. Для подтверждения данных и экспорта:

```bash
# Используя скрипт
./docker-approve.sh output/invoice_gemini_14120108_0errors.json invoice.jpg

# Или напрямую через docker-compose
docker-compose exec app python -m invoiceparser.app.main_cli approve --json /app/output/invoice_gemini_14120108_0errors.json --original-filename invoice.jpg
```

## Настройки Excel экспорта

Все настройки находятся в файле `.env`:

### Локальный Excel экспорт

```env
EXPORT_LOCAL_EXCEL_ENABLED=true
EXCEL_SHEET_HEADER_NAME=Реквизиты
EXCEL_SHEET_ITEMS_NAME=Позиции
EXCEL_HEADER_FIELD_COLUMN=Поле
EXCEL_HEADER_VALUE_COLUMN=Значение
EXCEL_DEFAULT_SHEET_NAME=Sheet
```

### Онлайн Excel (Google Sheets) экспорт

```env
EXPORT_ONLINE_EXCEL_ENABLED=true
SHEETS_SPREADSHEET_ID=1RgNqMHujYofrVq2YXXpEh0XUebO7xH0X2InYbBjrVL4
SHEETS_CREDENTIALS_PATH=/app/google_sheets_credentials.json
SHEETS_ITEMS_SHEET=Gemini
```

**Важно:**
- Файл `google_sheets_credentials.json` должен быть в корне проекта
- В Docker он монтируется как `/app/google_sheets_credentials.json`
- Если оба экспорта включены, они выполняются параллельно

## Структура проекта

```
invoice_parser/
├── invoices/          # Исходные документы для парсинга
├── output/            # Результаты парсинга (JSON, Excel)
├── logs/              # Логи приложения
├── .env               # Настройки приложения
├── docker-compose.yml # Конфигурация Docker
├── docker-parse.sh   # Скрипт для парсинга
└── docker-approve.sh  # Скрипт для подтверждения
```

## Проверка статуса

```bash
# Статус контейнеров
docker-compose ps

# Логи приложения
docker-compose logs app --tail=50

# Информация о конфигурации
docker-compose exec app python -m invoiceparser.app.main_cli info
```

