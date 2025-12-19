# Правила создания интерфейса

Файл `interface-rules.json` содержит все правила для динамического создания интерфейса.

## Структура правил

### 1. label_priority - Приоритет получения названий полей

Определяет порядок поиска названия поля:
1. `field_label_from_data` - из переданного параметра label
2. `key_suffix_label` - из поля `{key}_label` в родительском объекте
3. `nested_object_label` - из поля `_label` внутри объекта-значения
4. `field_labels_mapping` - из маппинга fieldLabels
5. `key_as_fallback` - сам ключ (только если ничего не найдено)

### 2. field_display_rules - Правила отображения полей

- `hide_fields` - какие поля скрывать (по суффиксам, префиксам, точным ключам)
- `show_empty_fields` - показывать ли пустые поля
- `skip_if_label_equals_key` - скрывать поле, если label равен ключу

### 3. sections - Правила для каждой секции

#### document_info
- `title_source: "static"` - использовать статический заголовок
- `title` - текст заголовка
- `process_nested_objects: "as_json"` - объекты показывать как JSON

#### parties
- `title_source: "from_data"` - заголовок брать из данных
- `use_label_from_data: true` - использовать _label из данных
- `label_cleanup` - очистка label (удаление ":", trim)

#### totals
- `numeric_fields` - правила для числовых полей
  - `show_in_words_below: true` - показывать прописью под числом
  - `in_words_suffix: "_in_words"` - суффикс для поля прописью
  - `in_words_source: "amounts_in_words"` - откуда брать прописью
  - `in_words_mapping` - маппинг ключей totals на amounts_in_words
  - `match_by_label_keywords` - поиск по ключевым словам в label

#### line_items (таблица товаров)
- `display_as: "table"` - отображать как таблицу
- `data_sources` - откуда брать данные (порядок проверки)
- `column_merge_rules` - правила слияния колонок
  - `merge_groups` - группы колонок для слияния
    - `target` - итоговое название колонки
    - `sources` - список исходных названий колонок
  - `use_label_from_data: true` - использовать _label из данных
- `column_order` - порядок колонок
  - `priority` - приоритетные колонки (в указанном порядке)
  - `then_others: true` - затем остальные

### 4. field_types - Правила для типов полей

- `boolean` - отображать как select (Да/Нет)
- `object` - как textarea с JSON
- `array` - как textarea с JSON
- `string` - как input, переключается на textarea если > 60 символов
- `number` - как input, форматировать в таблице

## Как редактировать правила

### Добавить новое правило слияния колонок:

```json
{
  "target": "Название колонки",
  "sources": ["key1", "key2", "key3"]
}
```

### Изменить приоритет получения label:

Измените порядок в массиве `priority` в `label_priority`.

### Добавить новую секцию:

Скопируйте структуру существующей секции и добавьте в `sections`.

### Изменить правила для числовых полей:

Измените `totals.numeric_fields`:
- `show_in_words_below` - показывать/скрывать прописью
- `in_words_mapping` - добавить новые маппинги
- `match_by_label_keywords` - добавить ключевые слова для поиска

## Важно

- Все текстовые значения (заголовки, названия) должны быть в конфиге для мультиязычности
- Правила используют логику, а не конкретные значения
- `_label` из данных всегда имеет приоритет над статическими значениями
- Правила применяются в указанном порядке













