# 🚀 Финальная архитектура БД - Быстрый старт

## 📦 Что в комплекте

### ✅ Основные файлы:

1. **`db_models_final.py`** (26KB) - SQLAlchemy модели
   - 14 таблиц
   - Поддержка неизвестных полей (field_id=NULL)
   - Таблица подписей (document_signatures)
   - Динамические таблицы (document_table_sections с column_mapping)
   - documents - минимальная без дублирования

2. **`db_service_final.py`** (22KB) - Сервис для работы с БД
   - `save_parsed_document()` - сохранение RAW данных
   - `save_approved_document()` - сохранение APPROVED данных
   - Автоматическая обработка неизвестных полей
   - Сохранение подписей из массива
   - Прямое сохранение column_mapping из промптов

3. **`alembic_migration_final.py`** (15KB) - Alembic миграция
   - Создает все таблицы
   - Индексы для быстрого поиска
   - Seed данные (типы документов)

4. **`COMPLETE_ARCHITECTURE_RU.md`** (30KB) - Полная документация
   - Ответы на ВСЕ вопросы
   - Примеры использования
   - SQL запросы

---

## 🎯 Что решает архитектура

### ✅ Проблема 1: Неизвестные поля
**Решение:** `field_id = NULL` в document_fields
```sql
-- Поиск неизвестных полей
SELECT * FROM document_fields WHERE field_id IS NULL;
```

### ✅ Проблема 2: Подписи/печати (1-20+)
**Решение:** Таблица `document_signatures`
```python
for idx, sig in enumerate(signatures_array):
    DocumentSignature(signature_index=idx, ...)
```

### ✅ Проблема 3: Дублирование в documents
**Решение:** documents минимальная (только ID, status, FK)
- ❌ НЕТ document_number, date, totals
- ✅ ВСЕ бизнес-данные в document_fields

### ✅ Проблема 4: Жесткие колонки в document_lines
**Решение:** JSONB в document_table_sections
```python
DocumentTableSection(
    column_mapping_raw={"no": "№", "tovar": "Товар"},  # из промпта!
    rows_raw=[{"no": 1, "tovar": "Motor"}]           # из промпта!
)
```

### ✅ Проблема 5: column_mapping из промптов
**Решение:** Прямое сохранение без преобразования!

---

## 🔧 Установка

### Шаг 1: Установить зависимости
```bash
pip install sqlalchemy asyncpg alembic psycopg2-binary
```

### Шаг 2: Настроить БД в config.py
```python
DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/invoiceparser"
```

### Шаг 3: Применить миграцию
```bash
# Скопировать в папку миграций
cp alembic_migration_final.py alembic/versions/001_final.py

# Применить
alembic upgrade head
```

### Шаг 4: Использовать в коде
```python
from db_service_final import DatabaseService

# Инициализация
db = DatabaseService(config.database_url)
await db.create_tables()  # если не используете Alembic

# После парсинга Gemini
async with await db.get_session() as session:
    document = await db.save_parsed_document(
        session=session,
        file_path=file_path,
        raw_json=gemini_result,
        doc_type_code="UA_INVOICE"
    )
    print(f"✅ Saved RAW: document_id={document.id}")

# После утверждения пользователем
async with await db.get_session() as session:
    await db.save_approved_document(
        session=session,
        document_id=document.id,
        approved_json=saved_json,
        user_id=user_id
    )
    print(f"✅ Saved APPROVED: document_id={document.id}")
```

---

## 📊 Структура БД

```
📁 МИНИМАЛЬНАЯ CORE (без бизнес-данных)
  └─ documents (ID, status, supplier_id, buyer_id)

📁 ВСЕ БИЗНЕС-ДАННЫЕ
  ├─ document_fields (известные + неизвестные)
  ├─ document_signatures (1-20+ подписей)
  └─ document_table_sections (column_mapping + rows)

📁 ИСТОРИЯ
  └─ document_snapshots (raw + approved версии)

📁 ОБУЧЕНИЕ
  ├─ companies (поставщики)
  └─ company_document_profiles (правила)
```

---

## 🔍 Примеры запросов

### Найти все неизвестные поля
```sql
SELECT raw_label, COUNT(*) as count
FROM document_fields
WHERE field_id IS NULL
GROUP BY raw_label
ORDER BY count DESC;
```

### Получить подписи документа
```sql
SELECT * FROM document_signatures
WHERE document_id = 123
ORDER BY signature_index;
```

### Получить таблицу с динамическими колонками
```sql
SELECT 
    column_mapping_raw,
    rows_raw
FROM document_table_sections
WHERE document_id = 123;
```

### Найти исправления для обучения
```sql
SELECT 
    field_code,
    COUNT(*) as corrections
FROM document_fields
WHERE is_corrected = TRUE
  AND document_id IN (
      SELECT id FROM documents WHERE supplier_id = 123
  )
GROUP BY field_code;
```

---

## ✨ Ключевые особенности

1. **Гибкость** - любой документ, язык, формат
2. **Масштабируемость** - миллионы документов
3. **Мультиязычность** - JSONB для колонок
4. **Human-in-the-Loop** - RAW + APPROVED
5. **Обучение** - is_corrected флаг
6. **Нет дублирования** - одна точка правды
7. **Промпты** - прямое использование column_mapping

---

## 📖 Документация

Читай **COMPLETE_ARCHITECTURE_RU.md** для:
- Детальных объяснений всех таблиц
- Примеров использования
- Ответов на вопросы
- SQL запросов

---

## 🚀 Готово к запуску!

Все решено, все документировано, все готово! 🎉
