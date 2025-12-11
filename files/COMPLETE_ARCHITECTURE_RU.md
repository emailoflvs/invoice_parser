# Полная архитектура базы данных для системы парсинга документов

## 📚 Содержание
1. [Обзор архитектуры](#обзор)
2. [Ответы на ключевые вопросы](#ответы-на-вопросы)
3. [Структура таблиц](#структура-таблиц)
4. [Поток данных](#поток-данных)
5. [Примеры использования](#примеры-использования)
6. [Масштабирование](#масштабирование)

---

## Обзор

Архитектура разработана с нуля с учетом всех требований:
- ✅ **RAW (сырые)** данные от AI
- ✅ **APPROVED (утвержденные)** данные после проверки
- ✅ **JSON снапшоты** для истории и аудита
- ✅ **Обучение на поставщиках** для автоматизации
- ✅ **Мультиязычность** и работа с любыми форматами
- ✅ **Масштабируемость** на миллионы документов
- ✅ **Неизвестные поля** - четкий механизм обработки
- ✅ **Подписи/печати** - от 1 до 20+ на документ
- ✅ **Динамические колонки** - через column_mapping из промптов

---

## Ответы на вопросы

### 1. ❓ Куда записывать НЕИЗВЕСТНЫЕ поля?

**Проблема:** AI находит поле, которого нет в справочнике.

**✅ Решение:** В таблицу `document_fields` с `field_id = NULL`

```sql
-- ИЗВЕСТНОЕ поле (есть в field_definitions):
INSERT INTO document_fields (
    document_id, field_id, field_code, raw_label, raw_value_text
) VALUES (
    123, 45, 'supplier_tax_id', 'ІПН', '374835510226'
);

-- НЕИЗВЕСТНОЕ поле (нет в справочнике):
INSERT INTO document_fields (
    document_id, field_id, field_code, raw_label, raw_value_text, section
) VALUES (
    123, NULL, NULL, 'Додаткова інформація', 'Термінова доставка', 'other'
    --   ^^^^  ^^^^  -- NULL = неизвестное поле!
);
```

**Поиск всех неизвестных полей:**
```sql
SELECT 
    raw_label,
    raw_value_text,
    COUNT(*) as occurrences
FROM document_fields
WHERE field_id IS NULL  -- индикатор неизвестного поля
GROUP BY raw_label, raw_value_text
ORDER BY occurrences DESC;
```

**Как сделать известным:**
```python
# 1. Добавить в справочник
new_field = FieldDefinition(
    code='special_instructions',
    section='other',
    data_type='text'
)

# 2. Обновить существующие записи
session.execute(
    update(DocumentField)
    .where(DocumentField.field_id == None)
    .where(DocumentField.raw_label == 'Додаткова інформація')
    .values(field_id=new_field.id, field_code='special_instructions')
)
```

---

### 2. ❓ Куда записывать 1-20 подписей/печатей?

**Проблема:** В JSON массив signatures с переменным количеством подписей.

**✅ Решение:** Новая таблица `document_signatures`

```sql
CREATE TABLE document_signatures (
    id                  BIGINT PRIMARY KEY,
    document_id         BIGINT FK -> documents,
    signature_index     INTEGER,              -- 0, 1, 2... (порядок)
    
    -- Данные подписи
    role                TEXT,                 -- "Бухгалтер", "Director"
    name                TEXT,                 -- ФИО
    is_signed           BOOLEAN,              -- есть подпись?
    is_stamped          BOOLEAN,              -- есть печать?
    stamp_content       TEXT,                 -- текст с печати
    handwritten_date    TEXT,                 -- дата от руки
    
    -- RAW vs APPROVED (как в полях!)
    raw_value           JSONB,
    approved_value      JSONB,
    is_corrected        BOOLEAN,
    
    -- Локация
    page_id             BIGINT FK,
    bbox                JSONB
);
```

**Пример сохранения:**
```python
signatures_array = json_data.get('signatures', [])

for idx, sig_data in enumerate(signatures_array):
    signature = DocumentSignature(
        document_id=doc_id,
        signature_index=idx,
        role=sig_data.get('role'),
        name=sig_data.get('name'),
        is_signed=sig_data.get('is_signed', False),
        is_stamped=sig_data.get('is_stamped', False),
        stamp_content=sig_data.get('stamp_content'),
        raw_value=sig_data  # весь JSON
    )
    session.add(signature)
```

---

### 3. ❓ Зачем `documents` отдельно, если все в `document_fields`?

**Ваш вопрос был правильным!** 🎯

**ПРОБЛЕМА в первой версии:**
```sql
-- Было дублирование:
documents:
    document_number     TEXT,     -- ❌ дублирует document_fields
    document_date       DATE,     -- ❌ дублирует document_fields
    total_with_vat      NUMERIC   -- ❌ дублирует document_fields
```

**✅ ИСПРАВЛЕНО - documents МИНИМАЛЬНАЯ:**
```sql
CREATE TABLE documents (
    id                  BIGINT PRIMARY KEY,
    file_id             BIGINT FK -> files,
    doc_type_id         INTEGER FK -> document_types,
    
    -- Статус и локализация
    status              VARCHAR(50),        -- parsed, approved, etc.
    language            VARCHAR(10),        -- uk, ru, en, fr
    country             VARCHAR(10),        -- UA, RU, FR
    
    -- ТОЛЬКО foreign keys (для быстрой фильтрации)
    supplier_id         BIGINT FK -> companies,
    buyer_id            BIGINT FK -> companies,
    
    -- Метаданные
    created_at          TIMESTAMP,
    created_by          BIGINT,
    updated_at          TIMESTAMP,
    parsing_metadata    JSONB
);

-- ⚠️ НЕТ document_number, date, totals!
-- ⚠️ ВСЕ бизнес-данные ТОЛЬКО в document_fields!
```

**Зачем тогда documents?**
1. **Быстрая фильтрация:** `WHERE supplier_id = 123`
2. **Workflow:** `WHERE status = 'in_review'`
3. **Метаданные:** `WHERE created_at > '2025-01-01'`

**Получение бизнес-данных:**
```sql
-- Номер документа:
SELECT approved_value_text 
FROM document_fields
WHERE document_id = 123 AND field_code = 'document_number';

-- НЕ из documents!
```

---

### 4. ❓ Жесткие колонки в document_lines - плохо для мультиязычности

**ПРОБЛЕМА в первой версии:**
```sql
-- Жесткие колонки только для Украины:
document_lines:
    product_code        TEXT,
    product_name        TEXT,
    ukt_zed             VARCHAR(20),  -- ❌ только для UA!
    quantity            NUMERIC,
    unit                VARCHAR(50),
    price_without_vat   NUMERIC       -- ❌ только для НДС!
```

**Не работает для:**
- Франции: "Code Douane", "Désignation", "Quantité"
- России: "Артикул", "Наименование", "Кол-во"
- США: "SKU", "Description", "Qty"

**✅ РЕШЕНИЕ: `document_table_sections` с JSONB**

```sql
CREATE TABLE document_table_sections (
    id                      BIGINT PRIMARY KEY,
    document_id             BIGINT FK -> documents,
    section_name            VARCHAR(100),  -- 'line_items', 'deliveries'
    
    -- Column mapping (точно как в промптах!)
    column_mapping_raw      JSONB,
    column_mapping_approved JSONB,
    
    -- Строки (ДИНАМИЧЕСКИЕ ключи!)
    rows_raw                JSONB,  -- массив объектов
    rows_approved           JSONB,
    
    is_corrected            BOOLEAN
);
```

**Украинский документ:**
```json
{
    "column_mapping_raw": {
        "no": "№",
        "ukt_zed": "УКТ ЗЕД",
        "tovar": "Товар",
        "kilkist": "Кількість",
        "tsina_bez_pdv": "Ціна без ПДВ"
    },
    "rows_raw": [
        {"no": 1, "ukt_zed": "8501510090", "tovar": "Motor", "kilkist": "2 шт", "tsina_bez_pdv": 4341.66}
    ]
}
```

**Французский документ:**
```json
{
    "column_mapping_raw": {
        "no": "№",
        "code_douane": "Code Douane",
        "designation": "Désignation",
        "quantite": "Quantité",
        "prix_ht": "Prix HT"
    },
    "rows_raw": [
        {"no": 1, "code_douane": "8501510090", "designation": "Moteur", "quantite": "2 pcs", "prix_ht": 4341.66}
    ]
}
```

**Работает для ЛЮБОГО языка!** ✅

---

### 5. ❓ Использовать column_mapping из промптов

**Из промпта:**
```
1. "column_mapping": {normalized_key: "Original Header"}
2. "line_items": [array of objects with keys from column_mapping]
```

**✅ В БД ТОЧНО ТАК ЖЕ:**

```python
# Из JSON (от AI):
table_data = {
    "column_mapping": {"no": "№", "tovar": "Товар"},
    "line_items": [{"no": 1, "tovar": "Motor"}]
}

# В БД (прямое сохранение):
DocumentTableSection(
    column_mapping_raw=table_data['column_mapping'],  # без изменений!
    rows_raw=table_data['line_items']                 # без изменений!
)
```

**Никакого преобразования! Один в один из промпта!** ✅

---

## Структура таблиц

### Иерархия архитектуры

```
┌─────────────────────────────────────────────────┐
│ МИНИМАЛЬНАЯ CORE (без бизнес-данных)           │
├─────────────────────────────────────────────────┤
│ documents                                       │
│  - ID, status, supplier_id, buyer_id, metadata  │
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ ВСЕ БИЗНЕС-ДАННЫЕ                               │
├─────────────────────────────────────────────────┤
│ document_fields                                 │
│  - Известные поля (field_id NOT NULL)          │
│  - Неизвестные поля (field_id = NULL)          │
│  - raw_value + approved_value                   │
│                                                 │
│ document_signatures                             │
│  - 1-20+ подписей/печатей                      │
│  - raw_value + approved_value                   │
│                                                 │
│ document_table_sections                         │
│  - column_mapping (JSONB)                       │
│  - rows (JSONB array)                           │
│  - Мультиязычные таблицы                       │
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ ИСТОРИЯ И АУДИТ                                 │
├─────────────────────────────────────────────────┤
│ document_snapshots                              │
│  - type: 'raw', 'approved'                      │
│  - version: 1, 2, 3...                          │
│  - payload: полный JSON                         │
└─────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────┐
│ ОБУЧЕНИЕ НА ПОСТАВЩИКАХ                         │
├─────────────────────────────────────────────────┤
│ companies + company_document_profiles           │
│  - Накопление знаний                            │
│  - Автоподстановка                              │
└─────────────────────────────────────────────────┘
```

### Детальная схема таблиц

#### 1. Справочники

```sql
-- Типы документов
document_types:
  id, code, name, description

-- Словарь полей
field_definitions:
  id, code, section, data_type, description

-- Переводы полей
field_labels:
  id, field_id, locale, label
```

#### 2. Компании (для обучения)

```sql
-- Справочник контрагентов
companies:
  id, legal_name, short_name
  tax_id, vat_id, registration_code
  country, language
  address_legal, address_postal
  iban, bank_name
  phone, email
  external_id, external_system
  is_verified
  created_at, updated_at

-- Профили обучения
company_document_profiles:
  id, company_id, doc_type_id
  is_active
  expected_currency, expected_vat_mode
  settings (JSONB)
  created_at, updated_at
```

#### 3. Файлы

```sql
-- Физические файлы
files:
  id, storage_path, original_filename
  file_hash, mime_type, size_bytes
  uploaded_at, uploaded_by

-- Страницы документов
document_pages:
  id, document_id, file_id
  page_number, ocr_text
  created_at
```

#### 4. Документы (минимальная core таблица)

```sql
documents:
  id, file_id, doc_type_id
  status, language, country
  supplier_id, buyer_id  -- только FK!
  created_at, created_by
  updated_at, updated_by
  parsing_metadata (JSONB)
  
-- ⚠️ БЕЗ бизнес-данных!
```

#### 5. Снапшоты (полные JSON)

```sql
document_snapshots:
  id, document_id
  snapshot_type, version
  payload (JSONB)
  created_at, created_by
  
-- UNIQUE(document_id, snapshot_type, version)
```

#### 6. Поля документа (все данные здесь!)

```sql
document_fields:
  id, document_id
  field_id, field_code  -- NULL для неизвестных!
  section, group_key
  raw_label, language
  
  -- RAW значения (от AI)
  raw_value_text, raw_value_number
  raw_value_date, raw_value_bool
  raw_confidence
  
  -- APPROVED значения (от человека)
  approved_value_text, approved_value_number
  approved_value_date, approved_value_bool
  approved_by, approved_at
  
  -- Контроль
  is_corrected, is_ignored
  
  -- Связи
  raw_snapshot_id, approved_snapshot_id
  page_id, bbox (JSONB)
  
  created_at, updated_at
```

#### 7. Подписи и печати

```sql
document_signatures:
  id, document_id, signature_index
  role, name
  is_signed, is_stamped
  stamp_content, handwritten_date
  raw_value (JSONB), approved_value (JSONB)
  is_corrected
  page_id, bbox (JSONB)
  created_at, updated_at
```

#### 8. Таблицы с динамическими колонками

```sql
document_table_sections:
  id, document_id
  section_name, section_order
  column_mapping_raw (JSONB)
  column_mapping_approved (JSONB)
  rows_raw (JSONB)
  rows_approved (JSONB)
  is_corrected
  approved_by, approved_at
  created_at, updated_at
```

---

## Поток данных

### Шаг 1: Парсинг документа (AI → RAW данные)

```python
# Gemini вернул JSON
raw_json = {
    "document_info": {"document_number": "755", ...},
    "parties": {"supplier": {...}, "customer": {...}},
    "totals": {...},
    "signatures": [{...}, {...}],
    "table_data": {
        "column_mapping": {...},
        "line_items": [...]
    }
}

# Сохраняем в БД
async with db.session() as session:
    document = await db.save_parsed_document(
        session, file_path, raw_json
    )
```

**Что создается в БД:**

```
1. File → запись о физическом файле
2. Document → status='parsed', supplier_id, buyer_id
3. DocumentSnapshot → type='raw', payload=raw_json
4. Companies → поставщик и покупатель (если новые)
5. DocumentField × N → все поля, только raw_*
6. DocumentSignature × N → все подписи, только raw_value
7. DocumentTableSection → column_mapping_raw, rows_raw
```

---

### Шаг 2: Модерация (человек проверяет)

Пользователь видит форму со всеми полями и может править:

```
Номер:     [755] ✓
Дата:      [2025-03-25] ✓
ИНН:       [3748355б] ✗ → исправил на [37483556]
Сумма:     [21919.97] ✓

Подпись 1: Бухгалтер - Галина ✓
Подпись 2: Отримав(ла) - Павло ✓

Таблица:
  Row 1: Motor-reductor ... ✓
  Row 2: Motor-reductor ... ✓
```

---

### Шаг 3: Сохранение после модерации (APPROVED данные)

```python
# Пользователь нажал "Сохранить"
saved_json = {
    # ... исправленные данные ...
}

async with db.session() as session:
    document = await db.save_approved_document(
        session, document_id, saved_json, user_id
    )
```

**Что обновляется в БД:**

```
1. Document → status='approved', updated_by=user_id
2. DocumentSnapshot → +1 запись: type='approved', payload=saved_json
3. DocumentField → approved_value_*, is_corrected=True (где изменилось)
4. DocumentSignature → approved_value, is_corrected (если правили)
5. DocumentTableSection → rows_approved (если правили таблицу)
```

**Теперь в БД:**
- RAW данные (как AI распарсил)
- APPROVED данные (как человек утвердил)
- История изменений (is_corrected=True)

---

## Примеры использования

### Пример 1: Сохранение документа с неизвестными полями

```python
async def save_document_with_unknown_fields():
    """Пример обработки известных и неизвестных полей"""
    
    # Парсинг вернул разные поля
    parsed_fields = [
        {"label": "ІПН", "value": "374835510226"},           # известное
        {"label": "Додаткова інформація", "value": "..."},   # неизвестное!
        {"label": "Special notes", "value": "..."}           # неизвестное!
    ]
    
    for field_data in parsed_fields:
        # Проверяем справочник
        field_def = await find_field_definition(field_data['label'])
        
        if field_def:
            # Известное поле
            field = DocumentField(
                document_id=doc_id,
                field_id=field_def.id,
                field_code=field_def.code,
                raw_label=field_data['label'],
                raw_value_text=field_data['value']
            )
        else:
            # ⚠️ НЕИЗВЕСТНОЕ поле
            field = DocumentField(
                document_id=doc_id,
                field_id=None,              # NULL!
                field_code=None,            # NULL!
                section='other',
                raw_label=field_data['label'],  # сохраняем оригинал
                raw_value_text=field_data['value']
            )
        
        session.add(field)
```

### Пример 2: Сохранение подписей

```python
async def save_signatures():
    """Пример сохранения 1-20 подписей"""
    
    signatures = json_data.get('signatures', [])
    
    for idx, sig in enumerate(signatures):
        signature = DocumentSignature(
            document_id=doc_id,
            signature_index=idx,
            role=sig.get('role'),
            name=sig.get('name'),
            is_signed=sig.get('is_signed', False),
            is_stamped=sig.get('is_stamped', False),
            stamp_content=sig.get('stamp_content'),
            handwritten_date=sig.get('handwritten_date'),
            raw_value=sig  # весь JSON для истории
        )
        session.add(signature)
```

### Пример 3: Сохранение таблицы (column_mapping)

```python
async def save_table_section():
    """Пример прямого сохранения из промпта"""
    
    table_data = json_data.get('table_data', {})
    
    # Прямое сохранение без преобразования!
    table_section = DocumentTableSection(
        document_id=doc_id,
        section_name='line_items',
        column_mapping_raw=table_data.get('column_mapping', {}),
        rows_raw=table_data.get('line_items', [])
    )
    session.add(table_section)
```

### Пример 4: Запрос неизвестных полей

```sql
-- Найти все неизвестные поля и их частоту
SELECT 
    raw_label,
    COUNT(*) as occurrences,
    COUNT(DISTINCT document_id) as documents_count,
    MAX(raw_value_text) as example_value
FROM document_fields
WHERE field_id IS NULL
GROUP BY raw_label
ORDER BY occurrences DESC;

-- Результат:
-- "Додаткова інформація" | 15 | 12 | "Термінова доставка"
-- "Special instructions"  | 8  | 7  | "Rush order"
```

### Пример 5: Запрос подписей документа

```python
async def get_document_signatures(doc_id):
    """Получить все подписи документа"""
    
    result = await session.execute(
        select(DocumentSignature)
        .where(DocumentSignature.document_id == doc_id)
        .order_by(DocumentSignature.signature_index)
    )
    signatures = result.scalars().all()
    
    for sig in signatures:
        print(f"Подпись #{sig.signature_index}")
        print(f"  Роль: {sig.role}")
        print(f"  Имя: {sig.name}")
        print(f"  Подписано: {sig.is_signed}")
        print(f"  Печать: {sig.is_stamped}")
```

### Пример 6: Работа с динамическими таблицами

```python
async def get_table_data(doc_id):
    """Получить данные таблицы с динамическими колонками"""
    
    result = await session.execute(
        select(DocumentTableSection)
        .where(
            DocumentTableSection.document_id == doc_id,
            DocumentTableSection.section_name == 'line_items'
        )
    )
    table = result.scalar_one()
    
    # Получаем column_mapping
    columns = table.column_mapping_approved or table.column_mapping_raw
    print(f"Колонки: {columns}")
    # {"no": "№", "tovar": "Товар", "kilkist": "Кількість"}
    
    # Получаем строки
    rows = table.rows_approved or table.rows_raw
    for row in rows:
        print(f"Row {row.get('no')}: {row.get('tovar')}")
```

### Пример 7: Поиск исправлений для обучения

```sql
-- Какие поля чаще всего исправляют для конкретного поставщика
SELECT 
    c.legal_name,
    df.field_code,
    COUNT(*) as correction_count,
    AVG(df.raw_confidence) as avg_ai_confidence
FROM document_fields df
JOIN documents d ON d.id = df.document_id
JOIN companies c ON c.id = d.supplier_id
WHERE df.is_corrected = TRUE
  AND c.id = 123
GROUP BY c.legal_name, df.field_code
ORDER BY correction_count DESC;

-- Результат: где AI чаще всего ошибается
-- "ТОВ ТЕХНО" | "supplier_iban" | 15 | 0.82
-- "ТОВ ТЕХНО" | "supplier_address" | 8 | 0.75
```

---

## Масштабирование

### Для миллионов документов

#### 1. Партиционирование

```sql
-- Партиционировать documents по created_at
CREATE TABLE documents_2025_q1 PARTITION OF documents
FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

CREATE TABLE documents_2025_q2 PARTITION OF documents
FOR VALUES FROM ('2025-04-01') TO ('2025-07-01');

-- Каскадное партиционирование для связанных таблиц
-- document_fields наследует партицию через document_id
```

#### 2. Индексы (уже в миграции)

```sql
-- Основные индексы
CREATE INDEX ix_documents_status ON documents(status);
CREATE INDEX ix_documents_supplier ON documents(supplier_id);
CREATE INDEX ix_documents_created ON documents(created_at);

-- Для document_fields
CREATE INDEX ix_document_fields_doc_section 
    ON document_fields(document_id, section);
CREATE INDEX ix_document_fields_code 
    ON document_fields(field_code);
CREATE INDEX ix_document_fields_corrected 
    ON document_fields(is_corrected);  -- для обучения!
CREATE INDEX ix_document_fields_unknown 
    ON document_fields(field_id);  -- NULL values для неизвестных
```

#### 3. Оптимизация запросов

```sql
-- Быстрый поиск по supplier_id (без JOIN)
SELECT * FROM documents 
WHERE supplier_id = 123 
  AND status = 'approved'
  AND created_at > '2025-01-01';

-- Детальные данные (с JOIN к полям)
SELECT d.*, df.*
FROM documents d
JOIN document_fields df ON df.document_id = d.id
WHERE d.id = 123;
```

#### 4. JSONB индексы (если нужно)

```sql
-- Для поиска в column_mapping
CREATE INDEX idx_table_column_mapping 
    ON document_table_sections USING gin(column_mapping_raw);

-- Для поиска в rows
CREATE INDEX idx_table_rows 
    ON document_table_sections USING gin(rows_raw);

-- Пример использования
SELECT * FROM document_table_sections
WHERE rows_raw @> '[{"tovar": "Motor"}]'::jsonb;
```

---

## Интеграция с существующим кодом

### В orchestrator.py

```python
from db_service import DatabaseService

# Инициализация
db = DatabaseService(config.database_url)

# После парсинга Gemini
gemini_result = await gemini_client.parse(file_path)

# Сохраняем RAW данные
async with await db.get_session() as session:
    document = await db.save_parsed_document(
        session=session,
        file_path=file_path,
        raw_json=gemini_result,
        doc_type_code="UA_INVOICE"
    )
    logger.info(f"✅ Saved RAW: document_id={document.id}")

# Когда пользователь утвердил
if user_approved:
    async with await db.get_session() as session:
        await db.save_approved_document(
            session=session,
            document_id=document.id,
            approved_json=saved_json,
            user_id=current_user.id
        )
        logger.info(f"✅ Saved APPROVED: document_id={document.id}")
```

---

## Преимущества финальной архитектуры

### ✅ Решает ВСЕ задачи

1. **✅ Неизвестные поля** → field_id=NULL в document_fields
2. **✅ Подписи (1-20+)** → document_signatures
3. **✅ Без дублирования** → documents минимальная
4. **✅ Мультиязычность** → JSONB column_mapping
5. **✅ Промпты** → прямое использование column_mapping
6. **✅ RAW vs APPROVED** → в каждой таблице
7. **✅ История** → document_snapshots
8. **✅ Обучение** → companies + is_corrected флаг

### ✅ Масштабируемость

- Партиционирование по дате
- Оптимальные индексы
- JSONB для гибкости
- Минимизация JOIN'ов

### ✅ Гибкость

- Любой тип документа
- Любой язык
- Любая структура таблиц
- Любое количество подписей

---

## Следующие шаги

1. **Запустить миграцию**
   ```bash
   alembic upgrade head
   ```

2. **Интегрировать в orchestrator**
   - Вызвать `save_parsed_document` после парсинга
   - Вызвать `save_approved_document` после модерации

3. **UI для модерации**
   - Показывать RAW vs APPROVED
   - Подсветка is_corrected=True
   - Работа с подписями и таблицами

4. **Система обучения**
   - Анализ is_corrected для каждого поставщика
   - Автоподстановка из company_document_profiles
   - Dashboard аналитики

---

## Заключение

Архитектура полностью готова и решает ВСЕ поднятые вопросы:

✅ Неизвестные поля  
✅ Подписи/печати  
✅ Без дублирования  
✅ Динамические колонки  
✅ Column_mapping из промптов  
✅ Мультиязычность  
✅ Масштабируемость  
✅ Обучение на поставщиках  

**Готово к запуску!** 🚀
