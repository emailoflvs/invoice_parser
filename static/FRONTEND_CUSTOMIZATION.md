# Настройка фронтенда

## 1. Изменение расположения формы загрузки

Файл: `static/style.css`

### Где находится:
- Строки 68-78: `.upload-section` и `.upload-card`

### Примеры изменений:

#### Центрирование формы:
```css
.upload-section {
    margin: 0 auto;
    max-width: 800px;
}
```

#### Форма слева:
```css
.upload-section {
    margin-left: 0;
    margin-right: auto;
    max-width: 600px;
}
```

#### Форма справа:
```css
.upload-section {
    margin-left: auto;
    margin-right: 0;
    max-width: 600px;
}
```

#### Абсолютное позиционирование:
```css
.upload-section {
    position: absolute;
    top: 100px;
    left: 50px;
    width: 500px;
}
```

#### Flexbox расположение:
```css
.container {
    display: flex;
    justify-content: center; /* или flex-start, flex-end, space-between */
    align-items: center;
}
```

## 2. Отображение `_label` вместо ключа

Файл: `static/script.js`

### Где находится:
- Строки 677-686: функция `getLabel()`
- Строки 689-710: функция `createField()`

### Как это работает:

Функция `getLabel()` теперь ищет `_label` в двух местах:

1. **Если значение само является объектом с `_label`:**
   ```json
   {
     "invoice_number": {
       "value": "123",
       "_label": "Номер накладной"
     }
   }
   ```
   Будет показано: "Номер накладной"

2. **Если есть отдельное поле `key + '_label'`:**
   ```json
   {
     "invoice_number": "123",
     "invoice_number_label": "Номер накладной"
   }
   ```
   Будет показано: "Номер накладной"

### Приоритет отображения:
1. Переданный `label` (если указан явно)
2. `_label` из данных (через `getLabel()`)
3. `fieldLabels[key]` (предопределенные украинские названия)
4. Сам `key` (если ничего не найдено)

### Если нужно изменить логику:

Отредактируйте функцию `getLabel()` в `static/script.js` (строки 677-686).

## Быстрая проверка изменений:

1. Сохраните файл
2. Обновите страницу в браузере (Ctrl+F5 для очистки кэша)
3. Изменения применятся сразу




