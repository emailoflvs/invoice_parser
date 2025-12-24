# Настройка автоматического тестирования фронтенда

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install playwright pytest-playwright httpx
playwright install chromium
```

### 2. Получение токена

```bash
# Вариант 1: Через curl (как на скриншоте)
curl -X POST "http://localhost:8000/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=YOUR_USERNAME&password=YOUR_PASSWORD" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" \
  > /tmp/test_token.txt

# Вариант 2: Через скрипт (автоматический логин)
python scripts/run_frontend_test.py
```

### 3. Запуск теста

```bash
# Полный визуальный тест (требует Playwright)
pytest tests/test_frontend_visual.py -v -s

# Упрощенный тест данных (без браузера)
pytest tests/test_frontend_data.py -v -s

# Через скрипт
./scripts/test_frontend_visual.sh
```

## Что тестируется

### test_frontend_data.py (быстрый, без браузера)
- ✅ Структура данных (column_order, line_items)
- ✅ Наличие колонки "no"
- ✅ Форматирование чисел
- ✅ Фильтрация служебных полей

### test_frontend_visual.py (полный, с браузером)
- ✅ Все из test_frontend_data.py
- ✅ Визуальное отображение в браузере
- ✅ CSS стили (overflow, text-overflow)
- ✅ Использование textarea для длинного текста
- ✅ Скриншот для анализа

## Результаты

После запуска создается временная директория:

```
/tmp/frontend_test_XXXXXX/
├── parse_result.json              # Результат парсинга через API
├── document_data.json              # Данные документа из БД
├── rendered_page.html              # HTML страницы (только visual test)
├── table_data.json                 # Данные таблицы
├── computed_styles.json            # Computed стили
├── table_screenshot.png            # Скриншот (только visual test)
├── detailed_table_report.json      # Детальный отчет
└── error_report.json               # Отчет об ошибках (если есть)
```

## Автоматизация

### Запуск после изменений фронтенда

Создайте `.git/hooks/pre-commit`:

```bash
#!/bin/bash
if git diff --cached --name-only | grep -qE "static/.*\.(js|css)$"; then
    echo "🧪 Тестирование фронтенда..."
    pytest tests/test_frontend_data.py -v
    if [ $? -ne 0 ]; then
        echo "❌ Тест не пройден. Отмена коммита."
        exit 1
    fi
fi
```

### CI/CD интеграция

```yaml
# .github/workflows/test.yml
- name: Frontend Tests
  run: |
    pip install playwright pytest-playwright httpx
    playwright install chromium
    pytest tests/test_frontend_data.py tests/test_frontend_visual.py -v
```

## Отладка

Если тест падает:

1. **Проверьте токен**: `cat /tmp/test_token.txt`
2. **Проверьте сервер**: `curl http://localhost:8000/health`
3. **Проверьте логи**: смотрите вывод pytest
4. **Проверьте сохраненные файлы**: смотрите путь в выводе теста

## Пример успешного запуска

```
📄 Парсинг документа: invoice.jpg
✅ Парсинг успешен. Document ID: 36

📥 Получение данных документа 36...

🔍 Анализ структуры данных...
   📋 column_order: ['no', 'ukt_zed', 'product_name', 'quantity', 'price_without_vat', 'amount_without_vat']
   ✅ 'no' найден в column_order на позиции 0
   📊 Найдено строк: 2
   ✅ Поле 'no' заполнено: '1'
   ✅ Длинный текст в 'product_name': 67 символов

✅ Ошибок в структуре данных не найдено!
```

