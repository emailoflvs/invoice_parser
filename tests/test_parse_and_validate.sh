#!/bin/bash

# Скрипт для тестирования парсинга и проверки редактируемых полей

echo "🧪 Тест парсинга invoice и проверка полей для редактирования"
echo ""

# Получаем токен из .env
TOKEN=$(grep WEB_AUTH_TOKEN .env | cut -d'=' -f2 | tr -d ' "')

if [ -z "$TOKEN" ]; then
    echo "❌ Токен WEB_AUTH_TOKEN не найден в .env"
    exit 1
fi

echo "📄 Отправляем lakover.jpg на парсинг..."
echo ""

# Отправляем файл на парсинг
RESPONSE=$(curl -s -X POST "http://localhost:8000/parse" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@invoices/lakover.jpg")

# Сохраняем в файл для анализа
echo "$RESPONSE" > /tmp/parse_response.json

# Проверяем успешность
SUCCESS=$(echo "$RESPONSE" | python3 -c "import json, sys; data=json.load(sys.stdin); print(data.get('success', False))" 2>/dev/null)

if [ "$SUCCESS" != "True" ]; then
    echo "❌ Парсинг не удался"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null | head -20
    exit 1
fi

echo "✅ Парсинг успешен!"
echo ""

# Проверяем структуру данных
echo "📋 Проверка полей для редактирования:"
echo ""

# Проверяем document_info
echo "1️⃣ document_info:"
echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
doc_info = data.get('data', {}).get('document_info', {})
if doc_info:
    for key, value in doc_info.items():
        if not key.endswith('_label'):
            print(f'  ✅ {key}: {str(value)[:50]}')
else:
    print('  ❌ document_info отсутствует')
" 2>/dev/null

echo ""

# Проверяем parties.supplier
echo "2️⃣ parties.supplier:"
echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
supplier = data.get('data', {}).get('parties', {}).get('supplier', {})
if supplier:
    for key, value in supplier.items():
        if not key.endswith('_label') and isinstance(value, (str, int, float)):
            print(f'  ✅ {key}: {str(value)[:50]}')
else:
    print('  ❌ parties.supplier отсутствует')
" 2>/dev/null

echo ""

# Проверяем parties.buyer
echo "3️⃣ parties.buyer:"
echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
buyer = data.get('data', {}).get('parties', {}).get('buyer', {})
if buyer:
    for key, value in buyer.items():
        if not key.endswith('_label') and isinstance(value, (str, int, float)):
            print(f'  ✅ {key}: {str(value)[:50]}')
else:
    print('  ❌ parties.buyer отсутствует')
" 2>/dev/null

echo ""

# Проверяем totals
echo "4️⃣ totals:"
echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
totals = data.get('data', {}).get('totals', {})
if totals:
    for key, value in totals.items():
        print(f'  ✅ {key}: {value}')
else:
    print('  ❌ totals отсутствует')
" 2>/dev/null

echo ""

# Проверяем line_items
echo "5️⃣ line_items (товары):"
ITEMS_COUNT=$(echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
items = data.get('data', {}).get('line_items', [])
print(len(items))
" 2>/dev/null)

echo "  Товаров: $ITEMS_COUNT"

if [ "$ITEMS_COUNT" -gt "0" ]; then
    echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
items = data.get('data', {}).get('line_items', [])
if items:
    print(f'  Пример первого товара:')
    for key, value in items[0].items():
        print(f'    • {key}: {str(value)[:40]}')
" 2>/dev/null
fi

echo ""

# Проверяем column_mapping
echo "6️⃣ column_mapping (для таблицы):"
echo "$RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
mapping = data.get('data', {}).get('column_mapping', {})
if mapping:
    for key, label in mapping.items():
        print(f'  ✅ {key} → {label}')
else:
    print('  ❌ column_mapping отсутствует')
" 2>/dev/null

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Итоговая проверка
echo "📊 Итоговая проверка совместимости с фронтендом:"
echo ""

python3 -c "
import json
with open('/tmp/parse_response.json') as f:
    data = json.load(f)

errors = []
warnings = []

# Проверяем обязательные секции
required_sections = {
    'document_info': ['document_type', 'document_number', 'document_date'],
    'parties': ['supplier', 'buyer'],
    'totals': ['total', 'vat', 'total_with_vat']
}

parsed_data = data.get('data', {})

# Проверяем document_info
if 'document_info' not in parsed_data:
    errors.append('Отсутствует document_info')
else:
    for field in required_sections['document_info']:
        if field not in parsed_data['document_info']:
            warnings.append(f'Поле document_info.{field} отсутствует')

# Проверяем parties
if 'parties' not in parsed_data:
    errors.append('Отсутствует parties')
else:
    if 'supplier' not in parsed_data['parties']:
        warnings.append('Отсутствует parties.supplier')
    if 'buyer' not in parsed_data['parties']:
        warnings.append('Отсутствует parties.buyer')

# Проверяем totals
if 'totals' not in parsed_data:
    warnings.append('Отсутствует totals')

# Проверяем товары
if 'line_items' not in parsed_data and 'items' not in parsed_data:
    warnings.append('Отсутствуют товары (line_items или items)')

# Проверяем column_mapping
if 'line_items' in parsed_data:
    if 'column_mapping' not in parsed_data:
        warnings.append('Отсутствует column_mapping для таблицы')

if errors:
    print('❌ Критические ошибки:')
    for error in errors:
        print(f'  • {error}')
    print()

if warnings:
    print('⚠️  Предупреждения:')
    for warning in warnings:
        print(f'  • {warning}')
    print()

if not errors and not warnings:
    print('✅ Все проверки пройдены!')
    print('✅ Фронтенд сможет отобразить все данные для редактирования')
elif not errors:
    print('✅ Структура в целом корректна')
    print('⚠️  Есть несущественные предупреждения')
else:
    print('❌ Обнаружены критические проблемы')
    print('❌ Фронтенд может работать некорректно')
" 2>/dev/null

echo ""
echo "💾 Полный ответ сохранен в: /tmp/parse_response.json"
echo "   Просмотр: cat /tmp/parse_response.json | python3 -m json.tool"

