#!/usr/bin/env python3
"""
Проверка, что все данные из API отображаются на фронтенде для редактирования
"""

import json
import sys

def check_editable_fields(response_file='/tmp/parse_response.json'):
    """Проверка полей для редактирования"""
    
    with open(response_file) as f:
        data = json.load(f)
    
    if not data.get('success'):
        print("❌ Парсинг не удался")
        return False
    
    parsed_data = data.get('data', {})
    
    print("🔍 Проверка данных для фронтенда:")
    print("=" * 60)
    print()
    
    all_ok = True
    
    # 1. Проверяем document_info
    print("1️⃣ document_info (Информация о документе):")
    doc_info = parsed_data.get('document_info', {})
    if doc_info:
        count = sum(1 for k in doc_info.keys() if not k.endswith('_label'))
        print(f"   ✅ {count} полей для редактирования")
        for key, value in doc_info.items():
            if not key.endswith('_label'):
                print(f"      • {key}")
    else:
        print("   ❌ Секция отсутствует")
        all_ok = False
    print()
    
    # 2. Проверяем parties
    print("2️⃣ parties (Стороны):")
    parties = parsed_data.get('parties', {})
    
    if parties:
        # Supplier
        supplier = parties.get('supplier', {})
        if supplier:
            count = sum(1 for k in supplier.keys() if not k.endswith('_label') and isinstance(supplier[k], (str, int, float)))
            print(f"   ✅ Поставщик: {count} полей")
            for key in supplier.keys():
                if not key.endswith('_label') and isinstance(supplier[key], (str, int, float)):
                    print(f"      • {key}")
        else:
            print("   ⚠️  Поставщик отсутствует")
        
        # Buyer
        buyer = parties.get('buyer', {})
        if buyer:
            count = sum(1 for k in buyer.keys() if not k.endswith('_label') and isinstance(buyer[k], (str, int, float)))
            print(f"   ✅ Покупатель: {count} полей")
            for key in buyer.keys():
                if not key.endswith('_label') and isinstance(buyer[key], (str, int, float)):
                    print(f"      • {key}")
        else:
            print("   ⚠️  Покупатель отсутствует (может быть в другой структуре)")
    else:
        print("   ❌ Секция parties отсутствует")
        all_ok = False
    print()
    
    # 3. Проверяем totals
    print("3️⃣ totals (Итоговые суммы):")
    totals = parsed_data.get('totals', {})
    if totals:
        count = len(totals)
        print(f"   ✅ {count} полей для редактирования")
        for key in totals.keys():
            print(f"      • {key}: {totals[key]}")
    else:
        print("   ⚠️  Секция отсутствует")
    print()
    
    # 4. Проверяем товары (line_items, items, table_data)
    print("4️⃣ Товары (для таблицы):")
    
    items = None
    column_mapping = None
    
    # Проверяем разные варианты
    if 'line_items' in parsed_data:
        items = parsed_data['line_items']
        column_mapping = parsed_data.get('column_mapping', {})
        source = "line_items"
    elif 'items' in parsed_data:
        items = parsed_data['items']
        column_mapping = parsed_data.get('column_mapping', {})
        source = "items"
    elif 'table_data' in parsed_data:
        table_data = parsed_data['table_data']
        items = table_data.get('line_items', table_data.get('items', []))
        column_mapping = table_data.get('column_mapping', {})
        source = "table_data"
    
    if items and len(items) > 0:
        print(f"   ✅ Найдено {len(items)} товаров (источник: {source})")
        print(f"   ✅ Поля в первом товаре:")
        for key in items[0].keys():
            print(f"      • {key}")
        
        if column_mapping:
            print(f"   ✅ column_mapping для таблицы:")
            for key, label in column_mapping.items():
                print(f"      • {key} → {label}")
        else:
            print("   ⚠️  column_mapping отсутствует (фронтенд использует имена полей)")
    else:
        print("   ❌ Товары не найдены")
        print("   💡 Проверьте структуру данных:")
        print(f"      Ключи верхнего уровня: {list(parsed_data.keys())}")
        all_ok = False
    print()
    
    # 5. Проверяем references
    print("5️⃣ references (Ссылки):")
    references = parsed_data.get('references', {})
    if references:
        count = len(references)
        print(f"   ✅ {count} полей")
        for key in references.keys():
            print(f"      • {key}")
    else:
        print("   ⚠️  Секция отсутствует (опционально)")
    print()
    
    # Итоговая оценка
    print("=" * 60)
    print()
    if all_ok:
        print("✅ ВСЕ ДАННЫЕ ГОТОВЫ ДЛЯ ОТОБРАЖЕНИЯ НА ФРОНТЕНДЕ")
        print("✅ Фронтенд сможет отобразить все редактируемые поля")
    else:
        print("⚠️  ЕСТЬ ПРОБЛЕМЫ С СТРУКТУРОЙ ДАННЫХ")
        print("⚠️  Часть полей может не отображаться на фронтенде")
    
    return all_ok


if __name__ == "__main__":
    check_editable_fields()

