# Улучшения рендеринга таблиц во фронтенде

## Дата: 19 декабря 2025

## Обзор изменений

Разработана улучшенная система отображения таблиц, которая **строго соблюдает порядок колонок из JSON** и **максимально улучшает визуализацию** без использования хардкода.

---

## 1. Строгое соблюдение порядка колонок из JSON

### Проблема
Ранее система могла терять порядок колонок при отображении, так как JavaScript объекты не всегда гарантируют порядок ключей (хотя современные браузеры сохраняют порядок вставки).

### Решение

#### Приоритеты получения порядка колонок:
1. **`data.table_data.column_order`** (предпочтительно) - явный массив, сохраняющий порядок
2. **`data.column_order`** (fallback на верхнем уровне)
3. **`Object.keys(column_mapping)`** (порядок ключей из маппинга)
4. **`Object.keys(firstItem)`** (последний вариант - из первой строки данных)

#### Логирование и валидация:
```javascript
console.log('✓ Using column order from table_data.column_order (explicit array):', allKeys);
console.log('=== TABLE COLUMN ORDER SUMMARY ===');
console.log(`Source: ${orderSource}`);
console.log(`Total columns: ${allKeys.length}`);
console.log(`Column order: [${allKeys.join(', ')}]`);
```

#### Проверка отсутствующих колонок:
Если колонка присутствует в `line_items`, но отсутствует в `column_order` или `column_mapping`, система выводит ошибку:
```
❌ CRITICAL: Unmapped columns found in line_items: [column_name]
❌ These columns exist in data but will NOT be displayed!
```

---

## 2. Визуальные улучшения таблицы

### 2.1 Контейнер таблицы

**Улучшения:**
- Плавная прокрутка для мобильных устройств (`-webkit-overflow-scrolling: touch`)
- Тень справа, показывающая, что есть дополнительный контент при горизонтальной прокрутке
- Адаптивный дизайн

```css
.table-container {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
}

.table-container::after {
    /* Shadow gradient on right edge when scrollable */
    content: '';
    position: absolute;
    right: 0;
    background: linear-gradient(to left, rgba(0,0,0,0.1), transparent);
    opacity: 0;
}

.table-container:not(.scrolled-to-end)::after {
    opacity: 1;
}
```

### 2.2 Стили таблицы

**Основные улучшения:**
- `border-collapse: separate` + `border-spacing: 0` для поддержки скругленных углов
- `font-variant-numeric: tabular-nums` для красивого выравнивания чисел
- Тень для объемного эффекта
- `overflow: hidden` для корректного отображения скругленных углов

```css
.editable-items-table {
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 8px;
    font-variant-numeric: tabular-nums;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
```

### 2.3 Заголовки таблицы

**Улучшения:**
- Sticky заголовок (`position: sticky; top: 0; z-index: 10`) - остается видимым при прокрутке
- Текстовая тень для лучшей читаемости на фиолетовом фоне
- Плавные переходы при наведении
- Интерактивный hover эффект

```css
.editable-items-table th {
    background: #7c3aed; /* Purple theme color */
    position: sticky;
    top: 0;
    z-index: 10;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
    transition: background-color 0.2s;
}

.editable-items-table th:hover {
    background: #6d28d9;
}
```

### 2.4 Строки таблицы

**Улучшения:**
- Hover эффект на всей строке для лучшего UX
- Zebra striping (чередующиеся цвета строк) для удобства чтения
- Плавные переходы цвета фона

```css
.editable-items-table tbody tr:hover td {
    background: #f8fafc;
}

.editable-items-table tbody tr:nth-child(even) td {
    background: #fafbfc;
}
```

### 2.5 Поля ввода (input)

**Улучшения:**
- Увеличен padding для комфортного редактирования
- Hover эффект для индикации интерактивности
- Focus состояние с тенью (ring effect)
- Плавные переходы
- Специальные стили для разных типов:
  - **Line numbers**: центрированные, жирный шрифт
  - **Numeric**: выравнивание по правому краю, моноширинные цифры

```css
.editable-items-table input {
    padding: 8px 10px;
    border: 1px solid #e2e8f0;
    transition: border-color 0.2s, box-shadow 0.2s;
}

.editable-items-table input:hover {
    border-color: #cbd5e1;
}

.editable-items-table input:focus {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.editable-items-table td.col-numeric input {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}
```

### 2.6 Текстовые области (textarea)

**Улучшения:**
- Минимальная высота 42px для комфортного редактирования
- Увеличенный line-height (1.5) для лучшей читаемости
- Hover и focus эффекты аналогичные input
- Вертикальный resize для длинных текстов

```css
.editable-items-table td textarea {
    min-height: 42px;
    line-height: 1.5;
    padding: 8px 10px;
    transition: border-color 0.2s, box-shadow 0.2s;
}
```

### 2.7 Адаптивная ширина колонок

**Динамический расчет min-width на основе типа колонки:**

```javascript
if (colType.type === 'line-number') {
    // Номера строк: минимальная ширина
    minWidthCh = Math.max(3, analysis.maxLength + 1);
} else if (colType.type === 'short-repetitive') {
    // Единицы измерения: компактная ширина
    minWidthCh = Math.max(5, analysis.maxLength + 2);
} else if (colType.type === 'numeric') {
    // Цены: учитываем длину заголовка
    const headerLength = safeLabel.length;
    minWidthCh = Math.max(8, Math.max(analysis.maxLength + 2, headerLength * 0.7));
} else if (colType.type === 'code') {
    // Коды товаров: средняя ширина
    minWidthCh = Math.max(10, Math.max(analysis.maxLength * 1.1, headerLength * 0.7));
} else if (colType.type === 'text') {
    // Описания: большая ширина с балансом
    minWidthCh = Math.max(20, Math.min(60, Math.max(analysis.avgLength * 0.8, headerLength * 0.8)));
}
```

**Особенности:**
- Учитывается как содержимое ячеек, так и длина заголовков
- Числовые колонки могут переноситься на 2 строки (например, "Ціна без\nПДВ")
- Используются `ch` единицы (ширина символа '0' в текущем шрифте)

### 2.8 Title атрибуты для длинных заголовков

Для заголовков длиннее 30 символов добавляется `title` атрибут - при наведении показывается полный текст:

```javascript
const titleAttr = safeLabel.length > 30 ? `title="${escapeHtml(safeLabel)}"` : '';
html += `<th ... ${titleAttr}>${escapeHtml(safeLabel)}</th>`;
```

---

## 3. Универсальность и отсутствие хардкода

### Ключевые принципы:

✅ **Все колонки и значения из JSON** - никаких примеров или фиксированных данных
✅ **Каждый JSON уникален** - система адаптируется к любой структуре
✅ **Порядок из документа** - строго соблюдается оригинальный порядок колонок
✅ **Автоматическая типизация** - определение типа колонки на основе содержимого
✅ **Мультиязычность** - работает с любым языком, без хардкода меток
✅ **Адаптивная ширина** - расчет ширины на основе анализа контента

### Валидация порядка:

```javascript
// Проверка на отсутствующие колонки
if (firstItem && typeof firstItem === 'object') {
    const itemKeys = Object.keys(firstItem).filter(/* ... */);
    const unmappedKeys = itemKeys.filter(k => !allKeys.includes(k));

    if (unmappedKeys.length > 0) {
        console.error('❌ CRITICAL: Unmapped columns found');
    }
}
```

---

## 4. Совместимость

### Браузеры:
- ✅ Chrome/Edge (последние версии)
- ✅ Firefox (последние версии)
- ✅ Safari (последние версии)
- ✅ Мобильные браузеры (iOS Safari, Chrome Mobile)

### Устройства:
- ✅ Desktop (1920x1080 и выше)
- ✅ Tablet (768x1024)
- ✅ Mobile (375x667 и выше)

### Особенности мобильных устройств:
- Плавная прокрутка (`-webkit-overflow-scrolling: touch`)
- Индикатор прокручиваемого контента (тень справа)
- Оптимизированные размеры touch-элементов (min 42px)

---

## 5. Тестирование

### Рекомендуется протестировать на примерах:

1. **invoice_gemini_thinking_2_prompts_v4.json** - базовая накладная (2 товара)
2. **lakover_gemini_thinking_2_prompts_v4.json** - накладная с длинным названием товара
3. **camozzi_gemini_thinking_2_prompts_v4.json** - накладная с множеством товаров (33+)

### Проверка порядка колонок:

1. Откройте DevTools (F12)
2. Перейдите на вкладку Console
3. Загрузите документ
4. Проверьте логи:
   ```
   ✓ Using column order from table_data.column_order: [...]
   === TABLE COLUMN ORDER SUMMARY ===
   ```
5. Убедитесь, что порядок колонок в таблице соответствует JSON

### Проверка отображения:

- [ ] Все колонки из JSON отображаются
- [ ] Порядок колонок соответствует JSON
- [ ] Заголовки корректно отображаются (с переносами, если нужно)
- [ ] Числа выравниваются по правому краю
- [ ] Длинные тексты корректно переносятся
- [ ] Hover эффекты работают
- [ ] Sticky заголовок работает при прокрутке
- [ ] Таблица адаптируется на мобильных устройствах

---

## 6. Файлы изменений

### Изменены:
- `static/script.js` - логика рендеринга таблицы
- `static/style.css` - стили таблицы

### Не изменены:
- `src/invoiceparser/services/post_processor.py` - уже поддерживает `column_order`
- `static/interface-rules.json` - правила остались без изменений

---

## 7. Дальнейшие улучшения (опционально)

1. **Сортировка таблицы** - добавить возможность сортировки по колонкам
2. **Фильтрация** - поиск по таблице
3. **Экспорт** - экспорт таблицы в CSV/Excel
4. **Валидация** - проверка корректности введенных данных
5. **История изменений** - отслеживание редактирования

---

## Заключение

Система теперь **максимально динамична**, **универсальна** и **строго соблюдает порядок из JSON**. Все визуальные улучшения сделаны без хардкода, с использованием автоматического анализа контента и адаптивного дизайна.


