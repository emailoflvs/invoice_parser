# ApprovedDataExportService

Сервис для экспорта утвержденных данных в различные форматы (Excel, Google Sheets и т.д.)

## Назначение

`ApprovedDataExportService` централизует логику экспорта утвержденных данных, позволяя использовать его из различных источников:
- Web API (через форму)
- Telegram Bot
- Email Poller
- CLI
- Другие источники данных

## Использование

### Базовый пример

```python
from invoiceparser.core.config import Config
from invoiceparser.services.approved_data_export_service import ApprovedDataExportService

# Инициализация
config = Config.load()
export_service = ApprovedDataExportService(config)

# Утвержденные данные (dict)
approved_data = {
    'header': {
        'invoice_number': 'INV-001',
        'date': '2024-01-15',
        'supplier_name': 'ООО "Поставщик"',
        'total_amount': 1000.00,
        # ... другие поля
    },
    'items': [
        {
            'name': 'Товар 1',
            'quantity': 10,
            'price': 100.00,
            'amount': 1000.00,
            # ... другие поля
        }
    ]
}

# Экспорт во все включенные форматы
results = await export_service.export_approved_data(
    approved_data=approved_data,
    original_filename='invoice_001.pdf'
)

# Проверка результатов
if results['excel']['success']:
    print(f"Excel экспортирован: {results['excel']['path']}")

if results['sheets']['success']:
    print("Данные сохранены в Google Sheets")
```

### Экспорт в конкретные форматы

```python
# Экспорт только в Excel
results = await export_service.export_approved_data(
    approved_data=approved_data,
    original_filename='invoice_001.pdf',
    export_formats=['excel']
)

# Экспорт только в Google Sheets
results = await export_service.export_approved_data(
    approved_data=approved_data,
    original_filename='invoice_001.pdf',
    export_formats=['sheets']
)
```

### Использование из разных источников

#### Web API
```python
# В web_api.py уже интегрировано
# Используется автоматически при сохранении через /save endpoint
```

#### Telegram Bot
```python
from invoiceparser.services.approved_data_export_service import ApprovedDataExportService

# После утверждения пользователем
export_service = ApprovedDataExportService(self.config)
results = await export_service.export_approved_data(
    approved_data=approved_data,
    original_filename=file_name
)
```

#### Email Poller
```python
from invoiceparser.services.approved_data_export_service import ApprovedDataExportService

# После обработки и утверждения из email
export_service = ApprovedDataExportService(self.config)
results = await export_service.export_approved_data(
    approved_data=approved_data,
    original_filename=attachment_name
)
```

#### CLI
```python
from invoiceparser.services.approved_data_export_service import ApprovedDataExportService

# После утверждения через CLI
export_service = ApprovedDataExportService(config)
results = await export_service.export_approved_data(
    approved_data=approved_data,
    original_filename=document_path.name
)
```

## Формат данных

Утвержденные данные должны быть в формате dict со следующей структурой:

```python
{
    'header': {
        'invoice_number': str,
        'date': str,  # ISO format
        'supplier_name': str,
        'buyer_name': str,
        'total_amount': float,
        # ... другие поля заголовка
    },
    'items': [
        {
            'name': str,
            'quantity': float,
            'price': float,
            'amount': float,
            # ... другие поля позиции
        }
    ]
}
```

Или альтернативный формат:

```python
{
    'header': {...},
    'table_data': {
        'line_items': [...]
    }
}
```

## Результат экспорта

Метод `export_approved_data` возвращает словарь с результатами:

```python
{
    'excel': {
        'success': bool,
        'path': Optional[Path],  # Путь к созданному Excel файлу
        'error': Optional[str]    # Сообщение об ошибке
    },
    'sheets': {
        'success': bool,
        'error': Optional[str]    # Сообщение об ошибке
    }
}
```

## Настройки

Экспорт управляется через переменные окружения в `.env`:

- `EXPORT_LOCAL_EXCEL_ENABLED=true` - включить экспорт в локальный Excel файл (.xlsx)
- `EXPORT_ONLINE_EXCEL_ENABLED=true` - включить экспорт в Google Sheets (онлайн Excel)
- `SHEETS_SPREADSHEET_ID=...` - ID таблицы Google Sheets
- `SHEETS_CREDENTIALS_PATH=...` - путь к credentials файлу

## Обработка ошибок

Сервис обрабатывает ошибки gracefully:
- Если экспорт в один формат не удался, другие форматы все равно экспортируются
- Ошибки логируются, но не прерывают выполнение
- Результаты экспорта возвращаются для каждого формата отдельно

