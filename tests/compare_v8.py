#!/usr/bin/env python3
"""
Скрипт для сравнения результатов v8 с эталонами (v7 thinking)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("compare_v8")

def compare_jsons(prog_data: Dict, chat_data: Dict, filename: str) -> List[Dict[str, Any]]:
    diffs = []

    # Убираем метаданные
    for k in ['test_results', '_meta']:
        prog_data.pop(k, None)
        chat_data.pop(k, None)

    # 1. Document Info
    p_doc = prog_data.get('document_info', {})
    c_doc = chat_data.get('document_info', {})

    # Сравниваем только важные поля
    # Игнорируем document_type, т.к. он может быть разным ("Счет", "Рахунок")
    for k in ['document_number', 'document_date', 'currency']:
        v1, v2 = p_doc.get(k), c_doc.get(k)
        # Нормализация для сравнения
        if v1: v1 = str(v1).strip()
        if v2: v2 = str(v2).strip()

        # Игнорируем отсутствие валюты в v8, если в v7 она была (v8 строже)
        if k == 'currency' and not v1 and v2:
            continue

        if v1 != v2:
            diffs.append({
                'type': 'document_info',
                'field': k,
                'program': v1,
                'reference': v2,
                'description': f"document_info.{k}: '{v1}' vs '{v2}'"
            })

    # 2. Parties
    # Тут сложнее, так как ключи ролей могут быть разными (supplier vs seller)
    # Но v8 пытается использовать standard keys.

    # Проверяем наличие _label (это требование v8)
    for role, data in prog_data.get('parties', {}).items():
        if isinstance(data, dict) and '_label' not in data:
             diffs.append({
                'type': 'v8_compliance',
                'field': f'parties.{role}._label',
                'program': 'MISSING',
                'reference': 'REQUIRED',
                'description': f"Party '{role}' is missing '_label' field"
            })

    # 3. Table Items
    p_items = prog_data.get('table_data', {}).get('line_items', [])
    c_items = chat_data.get('table_data', {}).get('line_items', [])

    if len(p_items) != len(c_items):
        diffs.append({
            'type': 'table_count',
            'field': 'line_items',
            'program': len(p_items),
            'reference': len(c_items),
            'description': f"Row count: {len(p_items)} vs {len(c_items)}"
        })

    # Сравниваем структуру колонок
    if p_items and c_items:
        p_cols = set(p_items[0].keys())
        c_cols = set(c_items[0].keys())

        # У v8 могут быть другие названия колонок (sku vs article, unit_price vs price_no_vat)
        # Это нормально, главное - наличие данных

        # Сравниваем значения (Article, Qty, Price)
        min_len = min(len(p_items), len(c_items))

        # Пытаемся найти ключ артикула (синонимы: article, sku, item_code)
        p_art = next((k for k in p_items[0] if any(x in k.lower() for x in ['article', 'sku', 'item_code', 'product_code'])), None)
        c_art = next((k for k in c_items[0] if any(x in k.lower() for x in ['article', 'sku', 'item_code', 'product_code'])), None)

        # Пытаемся найти ключ цены (синонимы: price, unit_price, price_no_vat)
        p_price = next((k for k in p_items[0] if 'price' in k.lower() and 'total' not in k.lower()), None)
        c_price = next((k for k in c_items[0] if 'price' in k.lower() and 'total' not in k.lower()), None)

        for i in range(min_len):
            # Артикул
            val_p = str(p_items[i].get(p_art, '')).strip().replace(' ', '')
            val_c = str(c_items[i].get(c_art, '')).strip().replace(' ', '')

            # Очистка от спецсимволов для мягкого сравнения
            val_p_clean = val_p.replace('.', '').replace('-', '').replace('/', '')
            val_c_clean = val_c.replace('.', '').replace('-', '').replace('/', '')

            if val_p_clean != val_c_clean:
                diffs.append({
                    'type': 'table_value',
                    'field': f'row_{i+1}.article',
                    'program': val_p,
                    'reference': val_c,
                    'description': f"Row {i+1} article: '{val_p}' vs '{val_c}'"
                })

            # Цена (только если есть в обоих)
            if p_price in p_items[i] and c_price in c_items[i]:
                # Простая проверка: числа должны совпадать
                try:
                    pr_p = float(str(p_items[i][p_price]).replace(',', '.').replace(' ', ''))
                    pr_c = float(str(c_items[i][c_price]).replace(',', '.').replace(' ', ''))
                    if abs(pr_p - pr_c) > 0.01:
                         diffs.append({
                            'type': 'table_value',
                            'field': f'row_{i+1}.price',
                            'program': pr_p,
                            'reference': pr_c,
                            'description': f"Row {i+1} price: {pr_p} vs {pr_c}"
                        })
                except:
                    pass

    return diffs

def main():
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "output"
    examples_dir = base_dir / "examples/gemini_thinking_2_prompts_v7"

    # Файлы v8
    v8_files = list(output_dir.glob("*_v8_test.json"))

    if not v8_files:
        logger.error("No v8 test files found in output/")
        return

    logger.info(f"Found {len(v8_files)} v8 files. Comparing...")

    total_diffs = 0

    for v8_file in v8_files:
        # Ищем пару
        base_name = v8_file.name.replace('_v8_test.json', '')
        ref_file = next(examples_dir.glob(f"{base_name}*.json"), None)

        if not ref_file:
            logger.warning(f"No reference for {base_name}")
            continue

        try:
            with open(v8_file, 'r') as f: p_data = json.load(f)
            with open(ref_file, 'r') as f: c_data = json.load(f)

            diffs = compare_jsons(p_data, c_data, base_name)

            print(f"\n📄 {base_name} ({len(diffs)} diffs)")
            if not diffs:
                print("   ✅ PERFECT MATCH")
            else:
                for d in diffs:
                    print(f"   ❌ {d['description']}")
                total_diffs += len(diffs)

        except Exception as e:
            logger.error(f"Error comparing {base_name}: {e}")

    print(f"\n{'='*40}")
    print(f"Total differences: {total_diffs}")

if __name__ == "__main__":
    main()


