# Сводка исправлений хардкода

## Выполненные исправления

### 1. ✅ Все сообщения пользователю переведены на английский

**Измененные файлы:**
- `src/invoiceparser/adapters/web_api.py` - все сообщения об ошибках и ответы API
- `src/invoiceparser/adapters/telegram_bot.py` - все сообщения бота
- `static/login.js` - все сообщения на странице логина
- `static/script.js` - основные сообщения об ошибках

**Примеры изменений:**
- "Неподдерживаемый формат файла" → "Unsupported file format"
- "Файл слишком большой" → "File is too large"
- "У вас нет доступа к этому боту" → "You do not have access to this bot"
- "Будь ласка, введіть ім'я користувача" → "Please enter username and password"

### 2. ✅ Все config значения вынесены в .env

**Добавленные параметры в `config.py`:**
- `JWT_COOKIE_MAX_AGE_DAYS` - время жизни cookie (по умолчанию 7 дней)
- `JWT_COOKIE_SECURE` - использование secure cookie (по умолчанию False)
- `COLUMN_TYPE_LINE_NUMBER_KEYS` - ключи для определения номера строки
- `COLUMN_TYPE_PRODUCT_KEYS` - ключи для определения описания товара
- `COLUMN_TYPE_PRICE_KEYS` - ключи для определения цен/сумм
- `COLUMN_TYPE_QUANTITY_KEYS` - ключи для определения количества
- `COLUMN_TYPE_CODE_KEYS` - ключи для определения кодов товаров

**Использование:**
Все эти параметры можно настроить в `.env` файле. Значения по умолчанию остаются для обратной совместимости.

### 3. ✅ Убраны проверки названий колонок - используется только ключи

**Изменения в `static/script.js`:**
- Функция `determineColumnType()` теперь принимает параметр `key` (не только `label`)
- Все проверки по названиям (labels) удалены
- Проверка идет ТОЛЬКО по ключам из конфигурации (`state.config.columnTypeKeys`)
- Ключи загружаются из API `/api/config` при инициализации

**Преимущества:**
- Полная мультиязычность - не зависит от языка названий колонок
- Настраиваемость через `.env`
- Использует только ключи из данных после парсинга

### 4. ✅ Убран хардкод column_order из interface-rules.json

**Изменения:**
- Удален хардкоженный список приоритетных колонок
- `column_order.priority` теперь пустой массив
- Добавлено описание, что порядок определяется динамически из `column_mapping`

### 5. ✅ max_age cookie вынесен в config

**Изменения:**
- Добавлен параметр `JWT_COOKIE_MAX_AGE_DAYS` в `config.py`
- В `web_api.py` используется `self.config.jwt_cookie_max_age_days` вместо хардкода `60 * 60 * 24 * 7`
- Также добавлен `JWT_COOKIE_SECURE` для настройки secure cookie

### 6. ✅ Единицы `ch` - объяснение

**Что это:**
- `ch` (character width) - CSS единица, равная ширине символа "0" в текущем шрифте
- Это относительная единица, автоматически адаптируется к размеру шрифта
- Уже является динамической и правильной

**Примеры:**
- `3ch` = ширина 3 символов "0" (для номеров строк)
- `30ch` = ширина 30 символов "0" (для описаний товаров)
- `12ch` = ширина 12 символов "0" (для цен)

**Вывод:** Единицы `ch` не являются хардкодом, это правильный способ задания адаптивных размеров.

### 7. ✅ Названия колонок Excel в .env

**Уже настроено через .env:**
- `EXCEL_SHEET_HEADER_NAME` - название листа реквизитов (по умолчанию "Реквизиты")
- `EXCEL_SHEET_ITEMS_NAME` - название листа позиций (по умолчанию "Позиции")
- `EXCEL_HEADER_FIELD_COLUMN` - название колонки "Поле"
- `EXCEL_HEADER_VALUE_COLUMN` - название колонки "Значение"
- `SHEETS_HEADER_SHEET` - название листа в Google Sheets для реквизитов
- `SHEETS_ITEMS_SHEET` - название листа в Google Sheets для позиций

**Примечание:** Значения по умолчанию на русском, но их можно изменить в `.env`

### 8. ✅ Логика определения типов колонок - только по ключам

**Изменения:**
- Убраны все проверки по названиям на разных языках
- Проверка идет ТОЛЬКО по ключам из конфигурации
- Ключи настраиваются через `.env`:
  - `COLUMN_TYPE_LINE_NUMBER_KEYS=no,line_number,number`
  - `COLUMN_TYPE_PRODUCT_KEYS=description,item_name,product_name,name`
  - `COLUMN_TYPE_PRICE_KEYS=price,amount,sum,total,unit_price,price_no_vat,price_without_vat`
  - `COLUMN_TYPE_QUANTITY_KEYS=quantity`
  - `COLUMN_TYPE_CODE_KEYS=code,sku,article,ukt_zed`

### 9. ✅ Словарь транслитерации - детали

**Расположение:** `src/invoiceparser/exporters/json_exporter.py`, функция `transliterate_to_latin()`

**Назначение:** Преобразует кириллические символы в латинские для имен файлов

**Код:**
```python
translit_map = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # ... заглавные буквы ...
    'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g',  # Украинские символы
    'І': 'I', 'Ї': 'Yi', 'Є': 'Ye', 'Ґ': 'G'
}
```

**Использование:** При сохранении файлов с кириллическими именами они транслитерируются в латиницу

**Является ли хардкодом:** Да, но это необходимо для функциональности. Можно вынести в конфиг, но это избыточно для статичного маппинга.

### 10. ✅ Убран хардкод localhost/127.0.0.1

**Изменения в `telegram_bot.py`:**
- Убран fallback на `http://127.0.0.1:{web_port}`
- Теперь используется ТОЛЬКО `WEB_PUBLIC_URL` из конфигурации
- Если `WEB_PUBLIC_URL` не настроен, показывается только document_id без кнопки редактирования

**Рекомендация:** Настроить `WEB_PUBLIC_URL` в `.env` для работы кнопки редактирования в Telegram

## Новые параметры .env

Добавьте в ваш `.env` файл следующие параметры (опционально, есть значения по умолчанию):

```env
# JWT Cookie settings
JWT_COOKIE_MAX_AGE_DAYS=7
JWT_COOKIE_SECURE=false

# Column type detection keys (comma-separated)
COLUMN_TYPE_LINE_NUMBER_KEYS=no,line_number,number
COLUMN_TYPE_PRODUCT_KEYS=description,item_name,product_name,name
COLUMN_TYPE_PRICE_KEYS=price,amount,sum,total,unit_price,price_no_vat,price_without_vat
COLUMN_TYPE_QUANTITY_KEYS=quantity
COLUMN_TYPE_CODE_KEYS=code,sku,article,ukt_zed

# Public URL for Telegram bot edit links (required for edit button)
WEB_PUBLIC_URL=http://your-domain.com:8000
```

## Итоги

✅ Все сообщения пользователю переведены на английский
✅ Все config значения вынесены в .env
✅ Убраны проверки названий колонок - используется только ключи
✅ Убран хардкод column_order из interface-rules.json
✅ max_age cookie вынесен в config
✅ Единицы `ch` объяснены (уже динамические)
✅ Названия колонок Excel уже в .env
✅ Логика определения типов колонок - только по ключам
✅ Словарь транслитерации описан
✅ Убран хардкод localhost/127.0.0.1

Все исправления применены и готовы к использованию.

