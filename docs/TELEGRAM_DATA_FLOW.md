# Поток данных из Telegram: от фото до подтверждения

## 📊 Полный цикл обработки

### 1. 📱 Получение фото из Telegram

```150:152:src/invoiceparser/adapters/telegram_bot.py
            elif update.message.photo:
                file = await update.message.photo[-1].get_file()
                file_name = f"photo_{update.message.photo[-1].file_id}.jpg"
```

**Что происходит:**
- Бот получает фото (берется самое большое разрешение)
- Файл сохраняется во временную директорию (`temp_dir`)
- Имя файла: `photo_{file_id}.jpg`

### 2. 🔄 Парсинг документа

```188:193:src/invoiceparser/adapters/telegram_bot.py
            # Обработка документа (передаем original_filename и mode как в веб-форме)
            # Используем режим "detailed" по умолчанию для Telegram (как в веб-форме)
            result = await self.orchestrator.process_document(
                tmp_path,
                original_filename=file_name,
                mode="detailed"
            )
```

**Важно:** Telegram бот теперь работает **точно так же**, как веб-форма:
- Передает `original_filename` для правильного сохранения в БД
- Использует режим `"detailed"` по умолчанию (как в веб-форме)
- Сохраняет данные в БД с теми же параметрами

**Процесс парсинга:**
1. **Препроцессинг:**
   - Для PDF: извлечение страниц в изображения
   - Для фото: улучшение качества, обрезка

2. **Парсинг через Gemini AI:**
   - Режим "detailed": 2 запроса (header + items) параллельно
   - Режим "fast": 1 запрос (комбинированный)
   - Извлечение всех данных из документа

3. **Post-processing:**
   - Нормализация чисел
   - Валидация данных
   - Структурирование результата

### 3. 💾 Сохранение RAW данных в БД

```120:127:src/invoiceparser/services/orchestrator.py
            # Сохранение RAW данных в базу данных
            document_id = None
            if self.db_service:
                try:
                    document_id = await self._save_raw_to_database(document_path, result, original_filename)
                    logger.info(f"✅ RAW data saved to database (document_id: {document_id})")
                except Exception as e:
                    logger.error(f"Failed to save RAW data to database: {e}", exc_info=True)
```

**Что сохраняется:**

#### Таблица `documents`:
- `id` - уникальный ID документа
- `status` - статус: `'parsed'` (после парсинга)
- `file_path` - путь к оригинальному файлу
- `original_filename` - имя файла
- `doc_type_code` - тип документа (автоопределение)
- `created_at` - время создания

#### Таблица `document_snapshots`:
- `snapshot_type = 'raw'` - тип снимка (RAW данные от AI)
- `payload` - **полный JSON с распарсенными данными**
- `document_id` - связь с документом
- `version = 1` - версия снимка

#### Таблица `document_fields`:
- Каждое поле из документа (header + items)
- `raw_value_*` - значения, извлеченные AI
- `field_code` - код поля (если известно)
- `raw_label` - оригинальный текст из документа

#### Таблица `document_table_sections`:
- Табличные данные (line_items)
- `rows_raw` - строки таблицы (RAW)
- `column_mapping_raw` - маппинг колонок (RAW)

**Важно:** Все RAW данные сохраняются автоматически после парсинга!

### 4. 📤 Отправка результата в Telegram

```195:219:src/invoiceparser/adapters/telegram_bot.py
            # Отправка результата
            if result["success"]:
                data = result["data"]

                # Формирование ответа
                response_text = (
                    "✅ Документ обработан успешно!\n\n"
                    f"📋 Номер счета: {data.header.invoice_number}\n"
                    f"📅 Дата: {data.header.date}\n"
                    f"🏢 Поставщик: {data.header.supplier_name}\n"
                    f"💰 Сумма: {data.header.total_amount}\n"
                    f"📦 Позиций: {len(data.items)}"
                )

                await status_message.edit_text(response_text)

                # Отправка JSON файла
                import json
                json_data = data.model_dump() if hasattr(data, "model_dump") else data
                json_str = json.dumps(json_data, indent=2, ensure_ascii=False)

                await update.message.reply_document(
                    document=json_str.encode('utf-8'),
                    filename=f"{data.header.invoice_number or 'result'}.json",
                    caption="📄 Полные данные в JSON"
                )
```

**Что отправляется:**
- Краткая информация о документе
- JSON файл с полными данными

### 5. ✅ Подтверждение данных (через Web API)

**RAW данные уже в БД!** Теперь нужно их подтвердить через веб-интерфейс.

#### Шаг 1: Поиск документа

```python
GET /api/search/documents
```

**Параметры:**
- `status=parsed` - найти необработанные документы
- `limit`, `offset` - пагинация

**Результат:**
- Список документов со статусом `'parsed'`
- Каждый документ содержит `document_id`

#### Шаг 2: Получение RAW данных

```python
GET /api/search/documents/{document_id}
```

**Результат:**
- Полный JSON с RAW данными
- Данные из `document_snapshots` где `snapshot_type='raw'`

#### Шаг 3: Редактирование и подтверждение

```python
POST /api/save
```

**Тело запроса:**
```json
{
  "document_id": 123,
  "data": {
    "header": { ... },
    "items": [ ... ]
  }
}
```

**Что происходит:**

```753:784:src/invoiceparser/adapters/web_api.py
    async def _save_approved_to_database(self, document_id: int, approved_data: dict, user_id: int) -> None:
        """
        Сохранение APPROVED данных в базу данных

        Args:
            document_id: ID документа в БД
            approved_data: Утвержденные данные
            user_id: ID пользователя, который утвердил данные
        """
        try:
            from ..database import get_session
            from ..database.service import DatabaseService

            # Создаем DatabaseService если еще нет
            db_service = DatabaseService(
                database_url=self.config.database_url,
                echo=self.config.db_echo,
                pool_size=self.config.db_pool_size,
                max_overflow=self.config.db_max_overflow
            )

            async for session in get_session():
                await db_service.save_approved_document(
                    session=session,
                    document_id=document_id,
                    approved_json=approved_data,
                    user_id=user_id
                )
                break
        except Exception as e:
            logger.error(f"Database approved save error: {e}", exc_info=True)
            raise
```

**Что сохраняется при подтверждении:**

#### Обновление `documents`:
- `status = 'approved'` - статус меняется на подтвержденный

#### Создание нового `document_snapshots`:
- `snapshot_type = 'approved'` - тип снимка (APPROVED данные)
- `payload` - **полный JSON с подтвержденными данными**
- `created_by = user_id` - кто подтвердил

#### Обновление `document_fields`:
- `approved_value_*` - подтвержденные значения
- `approved_by = user_id` - кто подтвердил
- `approved_at = timestamp` - когда подтвердили

#### Обновление `document_table_sections`:
- `rows_approved` - подтвержденные строки таблицы
- `column_mapping_approved` - подтвержденный маппинг колонок
- `approved_by = user_id`
- `approved_at = timestamp`

### 6. 📊 Структура данных в БД

#### RAW vs APPROVED

**RAW данные (от AI):**
- Сохраняются автоматически после парсинга
- Хранятся в `document_snapshots` с `snapshot_type='raw'`
- Поля: `raw_value_*` в `document_fields`
- Таблицы: `rows_raw` в `document_table_sections`

**APPROVED данные (от пользователя):**
- Сохраняются после подтверждения через Web API
- Хранятся в `document_snapshots` с `snapshot_type='approved'`
- Поля: `approved_value_*` в `document_fields`
- Таблицы: `rows_approved` в `document_table_sections`

**Важно:** Оба набора данных хранятся одновременно! Это позволяет:
- Сравнивать RAW и APPROVED
- Откатываться к RAW данным
- Анализировать качество парсинга

## 🔄 Полный поток данных

```
Telegram → Фото
    ↓
Временный файл (temp_dir)
    ↓
Orchestrator.process_document()
    ↓
Парсинг через Gemini AI
    ↓
_save_raw_to_database()
    ↓
БД: documents (status='parsed')
    ↓
БД: document_snapshots (type='raw')
    ↓
БД: document_fields (raw_value_*)
    ↓
БД: document_table_sections (rows_raw)
    ↓
Отправка результата в Telegram
    ↓
[Пользователь открывает Web UI]
    ↓
GET /api/search/documents (status='parsed')
    ↓
Редактирование данных
    ↓
POST /api/save (document_id, approved_data)
    ↓
_save_approved_to_database()
    ↓
БД: documents (status='approved')
    ↓
БД: document_snapshots (type='approved')
    ↓
БД: document_fields (approved_value_*)
    ↓
БД: document_table_sections (rows_approved)
    ↓
Экспорт в Excel/Google Sheets (только APPROVED)
```

## 📍 Где хранятся данные

### 1. **RAW данные (сырые, от AI):**
- **Таблица:** `document_snapshots` (snapshot_type='raw')
- **Таблица:** `document_fields` (raw_value_*)
- **Таблица:** `document_table_sections` (rows_raw)
- **Статус документа:** `documents.status = 'parsed'`

### 2. **APPROVED данные (подтвержденные, от пользователя):**
- **Таблица:** `document_snapshots` (snapshot_type='approved')
- **Таблица:** `document_fields` (approved_value_*)
- **Таблица:** `document_table_sections` (rows_approved)
- **Статус документа:** `documents.status = 'approved'`

### 3. **Файлы:**
- **Оригинальные файлы:** `invoices/` (если настроено)
- **JSON результаты:** `output/` (если настроено)
- **Временные файлы:** `temp/` (удаляются после обработки)

## ⚠️ Важные моменты

1. **Автоматическое сохранение RAW:**
   - RAW данные сохраняются автоматически после парсинга
   - Не требуется подтверждение для сохранения RAW

2. **Подтверждение через Web UI:**
   - Подтверждение происходит только через Web API
   - Telegram бот только парсит и сохраняет RAW

3. **Два набора данных:**
   - RAW и APPROVED хранятся отдельно
   - Можно сравнивать и анализировать различия

4. **Статусы документа:**
   - `'parsed'` - RAW данные сохранены, ожидает подтверждения
   - `'approved'` - данные подтверждены пользователем
   - `'rejected'` - данные отклонены
   - `'exported'` - данные экспортированы

5. **Экспорт:**
   - В Excel/Google Sheets экспортируются только APPROVED данные
   - RAW данные используются только для анализа

6. **Отмена подтверждения:**
   - Можно отменить подтверждение через `POST /api/reject`
   - Статус вернется в `'parsed'` для повторной проверки
   - APPROVED данные остаются в истории (не удаляются)

## 🔍 Как проверить данные в БД

```sql
-- Найти все RAW документы
SELECT id, original_filename, status, created_at
FROM documents
WHERE status = 'parsed';

-- Получить RAW данные документа
SELECT payload
FROM document_snapshots
WHERE document_id = 123 AND snapshot_type = 'raw';

-- Получить APPROVED данные документа
SELECT payload
FROM document_snapshots
WHERE document_id = 123 AND snapshot_type = 'approved';

-- Сравнить RAW и APPROVED поля
SELECT
    field_code,
    raw_value_text,
    approved_value_text
FROM document_fields
WHERE document_id = 123;
```

## ✅ Итог

**После отправки фото из Telegram:**
1. ✅ Файл парсится автоматически
2. ✅ RAW данные сохраняются в БД автоматически
3. ✅ Результат отправляется в Telegram
4. ⏳ Данные ожидают подтверждения через Web UI
5. ✅ После подтверждения создаются APPROVED данные

**Готово!** 🎉

