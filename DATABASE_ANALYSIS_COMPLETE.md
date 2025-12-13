# ПОЛНЫЙ АНАЛИЗ АРХИТЕКТУРЫ БД - СВОДНЫЙ ДОКУМЕНТ

Дата: 2025-12-13
Статус: БД пустая (0 bytes), проект в разработке
Требования: >1M записей, мультиязычность, универсальность для всех типов документов

==================================

## I. ТЕКУЩЕЕ СОСТОЯНИЕ БД

### Что уже реализовано

#### 1. Партиционирование (12 партиций)

- documents: RANGE по created_at (партиции: documents_2025, documents_2026)
- document_fields: HASH по document_id (4 партиции: p0, p1, p2, p3)
- document_snapshots: RANGE по created_at (партиции: 2025, 2026)
- document_table_sections: HASH по document_id (4 партиции: p0-p3)

#### 2. Индексы (19 индексов)

- B-Tree индексы:
  - documents: status, supplier_id, buyer_id, created_at, композитные индексы
  - document_fields: document_id+section, field_code, is_corrected, section_label
  - document_pages: document_id+page_number
  - companies: tax_id, vat_id, legal_name

- GIN индексы (FTS):
  - document_pages.ocr_text: simple, russian, english (3 индекса)
  - companies.legal_name: simple, russian, english (3 индекса)
  - documents.parsing_metadata: JSONB GIN
  - document_signatures.raw_value: JSONB GIN
  - company_document_profiles.settings: JSONB GIN

#### 3. Мультиязычность

- field_labels таблица с переводами (field_id + locale)
- section_label хранит оригинальный `_label` из JSON
- FTS индексы по 3 языкам для OCR и компаний

#### 4. Архитектура

- Гибридная EAV + JSONB схема
- RAW/APPROVED разделение
- Поддержка неизвестных полей (field_id=NULL)
- Динамические таблицы через column_mapping

==================================

## II. КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 1. ОТСУТСТВИЕ FOREIGN KEYS НА ПАРТИЦИОНИРОВАННЫХ ТАБЛИЦАХ

Статус: СПЕЦИАЛЬНО УБРАНО (не ошибка!)

Причина:

```sql
-- documents PRIMARY KEY: (id, created_at)
-- document_fields пытается ссылаться только на (id)
-- PostgreSQL требует: FK должен ссылаться на UNIQUE constraint, включающий partition key
```

Комментарий в миграции 004:

```python
# NOTE: Cannot create FOREIGN KEY on document_id because documents table is partitioned
# with PRIMARY KEY (id, created_at). PostgreSQL requires FK to reference unique constraint
# that includes partition key. We rely on application-level integrity instead.
```

Последствия:

- При удалении документа остаются "сиротские" записи в document_fields
- Нет автоматической очистки при удалении
- Риск потери целостности данных

Решение (если нужно):

- Добавить document_created_at в дочерние таблицы
- Создать составной FK: FOREIGN KEY (document_id, document_created_at) REFERENCES documents(id, created_at)

### 2. ОТСУТСТВИЕ FTS ИНДЕКСОВ НА document_fields.raw_value_text

Статус: НЕ РЕАЛИЗОВАНО

Текущее состояние:

- FTS индексы есть для document_pages.ocr_text (3 языка)
- FTS индексы есть для companies.legal_name (3 языка)
- FTS индексов НЕТ для document_fields.raw_value_text

Проблема:

```python
# В search_documents_by_text() используется:
func.to_tsvector(language, func.coalesce(DocumentField.raw_value_text, ''))
# Но индекса нет → Sequential Scan на 50M записей!
```

Последствия:

- Поиск по полям документов будет очень медленным (производительность зависит от объема данных)
- Метод search_documents_by_text() неэффективен

Решение:

```sql
-- Добавить GIN индексы:
CREATE INDEX idx_document_fields_raw_value_fts_simple
ON document_fields USING GIN (to_tsvector('simple', COALESCE(raw_value_text, '')));

-- Partial индексы по языкам (опционально):
CREATE INDEX idx_document_fields_raw_value_fts_ru
ON document_fields USING GIN (to_tsvector('russian', COALESCE(raw_value_text, '')))
WHERE language IN ('ru', 'uk');
```

### 3. ОТСУТСТВИЕ GIN ИНДЕКСОВ НА JSONB ПОЛЯХ document_table_sections

Статус: НЕ РЕАЛИЗОВАНО

Текущее состояние:

- Метод search_documents_by_table_value() существует
- GIN индексов на rows_raw и rows_approved НЕТ

Проблема:

```python
# В search_documents_by_table_value() используется:
jsonb_array_elements(dts.rows_raw) AS row WHERE row @> :search_pattern::jsonb
# Без индекса → медленный поиск
```

Последствия:

- Поиск по содержимому таблиц (например, "найти все документы с товаром SKU='ABC123'") будет медленным

Решение:

```sql
CREATE INDEX idx_table_sections_rows_raw_gin
ON document_table_sections USING GIN (rows_raw jsonb_path_ops);

CREATE INDEX idx_table_sections_rows_approved_gin
ON document_table_sections USING GIN (rows_approved jsonb_path_ops);
```

### 4. НЕТ АВТОМАТИЧЕСКОГО СОЗДАНИЯ ПАРТИЦИЙ

Статус: НЕ РЕАЛИЗОВАНО (но миграция создана: 008_auto_create_partitions.py)

Проблема:

- Партиции documents_2025, documents_2026 созданы вручную
- КРИТИЧНО: При вставке данных с датой, для которой нет партиции, система упадет с ошибкой: "no partition of relation documents found"
- Это приведет к полной остановке записи данных в production

Решение:

- Миграция 008_auto_create_partitions.py создана
- Триггер автоматически создает партиции при INSERT в новый год
- ВАЖНО: Применить миграцию ДО запуска в production

### 5. ОТСУТСТВИЕ ДЕНОРМАЛИЗАЦИИ КЛЮЧЕВЫХ ПОЛЕЙ

Статус: НЕ РЕАЛИЗОВАНО

Проблема:

- Таблица documents содержит ТОЛЬКО метаданные
- Для получения total_amount, invoice_number, invoice_date нужен JOIN к document_fields
- При 1M документов каждый дашборд = сложный запрос

Решение:

```sql
-- Добавить в documents:
ALTER TABLE documents ADD COLUMN invoice_number VARCHAR(100);
ALTER TABLE documents ADD COLUMN invoice_date DATE;
ALTER TABLE documents ADD COLUMN total_amount NUMERIC(30, 10);
ALTER TABLE documents ADD COLUMN currency CHAR(3);
ALTER TABLE documents ADD COLUMN supplier_name TEXT;
ALTER TABLE documents ADD COLUMN buyer_name TEXT;

-- Обновлять при парсинге в DatabaseService.save_parsed_document()
```

### 6. ДУБЛИКАТЫ КОМПАНИЙ

Статус: ПРОБЛЕМА ВЫЯВЛЕНА

Текущее состояние:

- Логика нормализации есть: _extract_and_link_companies()
- Поиск по tax_id: find_company_by_tax_id()
- Обновление существующих: create_or_update_company()

Проблема:

```text
ID 1, 4, 6 - одна компания "ТЕХНО - ПРИВІД", но разные записи:
- ID 1: tax_id = NULL
- ID 4: tax_id = '37483556'
- ID 6: tax_id = 'код за ЄДРПОУ 37483556' (с префиксом)

ID 3, 5, 7, 8, 9, 10 - одна "ІНФОРМАЦІЙНА КОМПАНІЯ", но разные записи
```

Причины:

1. tax_id не всегда заполнен или различается форматированием
2. Поиск ТОЛЬКО по tax_id (если NULL → создается дубликат)
3. Нет нормализации названий (регистр, префиксы)

Решение:

```python
# 1. Нормализовать tax_id перед поиском:
def normalize_tax_id(tax_id: str) -> str:
    import re
    numbers = re.findall(r'\d+', tax_id)
    return numbers[0] if numbers else None

# 2. Поиск по имени, если tax_id отсутствует:
if not tax_id:
    normalized_name = normalize_company_name(name)
    company = await self.find_company_by_name(session, normalized_name)
```

==================================

## III. СРЕДНИЕ ПРОБЛЕМЫ

### 7. Размер document_pages.ocr_text

- PDF на 100 страниц = 1MB на документ
- При 1M документов = 1TB только OCR текста
- Решение: Compression или S3/MinIO

### 8. Нет защиты от "шторма" дублей

- UNIQUE constraint на file_hash удален (бизнес-требование)
- Если пользователь кликнет "Парсить" 10 раз → 10 идентичных документов
- Решение: Проверка recent duplicates (окно настраивается через DUPLICATE_CHECK_WINDOW_SECONDS в .env)

==================================

## IV. СРАВНЕНИЕ С ПРЕДЫДУЩИМИ АНАЛИЗАМИ

| Аспект | GPT Codex | Gemini | МОЙ АНАЛИЗ | СТАТУС |
|--------|-----------|---------|-------------|--------|
| FK проблема | Упомянул, триггеры | Упомянул, created_at в дочерних | Детальное SQL-решение | Объяснено: специально убрано |
| FTS индексы | Упомянул GIN | Упомянул, но без деталей | Конкретные индексы | Частично: нет для document_fields |
| Денормализация | Предложил summary | Предложил 5-10 полей | Конкретная схема + код | Не реализовано |
| Партиции | Не упомянул авто-создание | Упомянул мониторинг | Триггер для авто-создания | Миграция создана, но НЕ ПРИМЕНЕНА (критично!) |
| Дубли | Упомянул проблему | Предложил soft-check | Конкретный код | Проблема с компаниями |
| JSONB индексы | Не упомянул | Не упомянул | GIN индексы для rows_raw | Не реализовано |
| Companies | Не упомянул | Не упомянул | Детальный анализ дублей | Проблема выявлена |

==================================

## V. ИТОГОВЫЙ СПИСОК ДЕЙСТВИЙ

### КРИТИЧНО (сделать ДО запуска в production)

1. Применить миграцию авто-создания партиций (ПРИОРИТЕТ #1)
   - 008_auto_create_partitions.py уже создана
   - БЕЗ ЭТОГО система упадет при вставке данных с датой, для которой нет партиции
   - Запустить alembic upgrade head
   - Триггер автоматически создает партиции при INSERT в новый год

2. Добавить FTS индексы на document_fields.raw_value_text
   - GIN индексы по языкам (simple, russian, english)
   - Partial индексы по language для оптимизации
   - Без этого поиск будет очень медленным (производительность зависит от объема данных)

3. Добавить GIN индексы на document_table_sections.rows_raw/rows_approved
   - Для быстрого поиска по содержимому таблиц
   - Без этого поиск по товарам/позициям будет медленным

4. Исправить дубликаты компаний
   - Нормализация tax_id (убрать префиксы)
   - Поиск по имени, если tax_id отсутствует
   - Нормализация названий (регистр)

### ВАЖНО (сделать в первые месяцы)

1. Денормализовать ключевые поля в documents
   - invoice_number, invoice_date, total_amount, currency, supplier_name, buyer_name
   - Обновлять при парсинге

2. Защита от шторма дублей
   - Проверка recent duplicates (окно настраивается через DUPLICATE_CHECK_WINDOW_SECONDS в .env)
   - Advisory locks при парсинге

### ЖЕЛАТЕЛЬНО (когда БД вырастет)

1. Оптимизация хранения OCR
   - Compression для document_pages.ocr_text
   - Или миграция в S3 с async загрузкой

2. Материализованные представления для дашбордов

3. Архивирование старых партиций
   - Партиции старше N лет (настраивается через ARCHIVE_PARTITIONS_OLDER_THAN_YEARS в .env)

==================================

## VI. ОЦЕНКА ТЕКУЩЕЙ АРХИТЕКТУРЫ

| Критерий | Оценка | Комментарий |
|----------|--------|-------------|
| Масштабируемость (1M+ записей) | 4/5 | Партиционирование есть, но нет FTS и JSONB индексов |
| Мультиязычность | 4/5 | Отличная поддержка, нужны языковые индексы на fields |
| Универсальность | 5/5 | Гибридная схема идеальна |
| Производительность | 3/5 | Без денормализации и FTS - проблемы |
| Целостность данных | 3/5 | Нет FK (специально), но есть дубликаты компаний |
| ИТОГО: | 3.8/5 | Хорошая база, нужны доработки |

==================================

## VII. ДЕТАЛИ ПО КОМПАНИЯМ

### Текущая логика

```python
# _extract_and_link_companies():
1. Извлекает supplier/buyer из JSON (поддерживает dict и array форматы)
2. Ищет компанию по tax_id: find_company_by_tax_id()
3. Если найдена - обновляет, если нет - создает новую
```

### Проблемы

1. Поиск только по tax_id:

   - Если tax_id = NULL → всегда создается новая компания
   - Если tax_id различается форматированием → дубликаты

2. Нет нормализации:

   - tax_id = '37483556' vs tax_id = 'код за ЄДРПОУ 37483556' → разные компании
   - legal_name = 'ТОВАРИСТВО...' vs legal_name = 'Товариство...' → разные компании

3. Результат:

   - 10 компаний в БД, но реально только 4 уникальных
   - Документы ссылаются на разные ID одной и той же компании

### Решение

```python
# 1. Нормализовать tax_id:
def normalize_tax_id(tax_id: str) -> str:
    if not tax_id:
        return None
    import re
    numbers = re.findall(r'\d+', tax_id)
    return numbers[0] if numbers else None

# 2. Поиск по нормализованному tax_id:
normalized_tax_id = normalize_tax_id(tax_id)
if normalized_tax_id:
    company = await self.find_company_by_tax_id(session, normalized_tax_id)

# 3. Если tax_id нет, искать по нормализованному имени:
if not company:
    normalized_name = normalize_company_name(name)  # lowercase, убрать префиксы
    company = await self.find_company_by_name(session, normalized_name)
```

==================================

## VIII. ФАЙЛЫ И МИГРАЦИИ

### Существующие миграции

- 003_table_partitioning.py - партиционирование documents
- 004_partition_related_tables.py - партиционирование связанных таблиц (FK убраны)
- 005_allow_duplicate_file_hashes.py - удален UNIQUE на file_hash
- 006_populate_field_definitions.py - заполнение справочников
- 007_add_section_label.py - добавлено поле section_label

### Созданные, но не примененные

- 008_auto_create_partitions.py - авто-создание партиций (триггеры)

### Нужно создать

- 009_add_fts_indexes.py - FTS индексы для document_fields
- 010_add_jsonb_indexes.py - GIN индексы для document_table_sections
- 011_denormalize_documents.py - денормализация ключевых полей
- 012_fix_company_duplicates.py - нормализация компаний

==================================

## VIII-A. ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ДЛЯ БД

### Новые переменные в config.py (добавлены для устранения хардкода)

```python
# Database maintenance settings
archive_partitions_older_than_years: int = Field(
    alias="ARCHIVE_PARTITIONS_OLDER_THAN_YEARS",
    default=2
)  # Архивировать партиции старше N лет

duplicate_check_window_seconds: int = Field(
    alias="DUPLICATE_CHECK_WINDOW_SECONDS",
    default=60
)  # Окно проверки дублей при парсинге (в секундах)
```

### Пример .env

```env
# Database maintenance
ARCHIVE_PARTITIONS_OLDER_THAN_YEARS=2
DUPLICATE_CHECK_WINDOW_SECONDS=60
```

### Использование

- `ARCHIVE_PARTITIONS_OLDER_THAN_YEARS` - используется для определения, какие партиции архивировать (по умолчанию: 2 года)
- `DUPLICATE_CHECK_WINDOW_SECONDS` - используется для защиты от "шторма дублей" при парсинге (по умолчанию: 60 секунд)

==================================

## IX. ВЫВОДЫ

### Сильные стороны

1. Партиционирование внедрено правильно
2. Гибридная EAV + JSONB схема идеальна для универсальности
3. Мультиязычность хорошо поддержана
4. RAW/APPROVED разделение для ML-обучения

### Слабые стороны

1. Нет FTS индексов на document_fields → медленный поиск
2. Нет GIN индексов на JSONB → медленный поиск по таблицам
3. Нет денормализации → медленные дашборды
4. Дубликаты компаний → потеря нормализации

### Приоритеты

1. КРИТИЧНО #1: Автоматическое создание партиций (без этого система упадет при вставке данных с датой, для которой нет партиции)
2. КРИТИЧНО #2: FTS и JSONB индексы (влияют на производительность)
3. ВАЖНО: Денормализация и исправление дублей компаний
4. ЖЕЛАТЕЛЬНО: Оптимизация хранения и архивирование
