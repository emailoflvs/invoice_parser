#!/usr/bin/env python3
"""
Поиск 10 лучших файлов dnipromash по качеству данных
Сравнение важных бизнес-полей с эталоном
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple

def compare_business_fields(result_data: Dict, ref_data: Dict) -> Dict[str, Any]:
    """Сравнивает важные бизнес-поля и возвращает статистику ошибок"""

    result_items = result_data.get('table_data', {}).get('line_items', [])
    ref_items = ref_data.get('table_data', {}).get('line_items', [])

    if not result_items or not ref_items:
        return {'error': 'Empty items'}

    # Находим ключи в результате
    result_keys = {}
    for k in result_items[0].keys():
        k_lower = k.lower()
        if any(x in k_lower for x in ['article', 'sku', 'item_code']):
            result_keys['article'] = k
        elif any(x in k_lower for x in ['price', 'unit_price', 'price_without', 'price_excl']):
            result_keys['price'] = k
        elif any(x in k_lower for x in ['quantity', 'qty']):
            result_keys['quantity'] = k
        elif any(x in k_lower for x in ['amount', 'sum', 'total', 'amount_without', 'total_without']):
            result_keys['amount'] = k

    # Находим ключи в эталоне
    ref_keys = {}
    for k in ref_items[0].keys():
        k_lower = k.lower()
        if any(x in k_lower for x in ['article', 'sku']):
            ref_keys['article'] = k
        elif any(x in k_lower for x in ['price', 'unit_price']):
            ref_keys['price'] = k
        elif any(x in k_lower for x in ['quantity', 'qty']):
            ref_keys['quantity'] = k
        elif any(x in k_lower for x in ['amount', 'sum', 'total']):
            ref_keys['amount'] = k

    min_len = min(len(result_items), len(ref_items))

    errors = {
        'article': [],
        'price': [],
        'quantity': [],
        'amount': []
    }

    # Сравниваем артикулы
    if result_keys.get('article') and ref_keys.get('article'):
        for i in range(min_len):
            result_art = str(result_items[i].get(result_keys['article'], '')).strip()
            ref_art = str(ref_items[i].get(ref_keys['article'], '')).strip()

            result_clean = result_art.replace(' ', '').replace('.', '').replace('-', '')
            ref_clean = ref_art.replace(' ', '').replace('.', '').replace('-', '')

            if result_clean != ref_clean:
                errors['article'].append({
                    'row': i + 1,
                    'result': result_art,
                    'reference': ref_art
                })

    # Сравниваем цены
    if result_keys.get('price') and ref_keys.get('price'):
        for i in range(min_len):
            result_price = result_items[i].get(result_keys['price'])
            ref_price = ref_items[i].get(ref_keys['price'])

            # Нормализуем цены
            try:
                result_val = float(str(result_price).replace(',', '.').replace(' ', ''))
                ref_val = float(str(ref_price).replace(',', '.').replace(' ', ''))
                if abs(result_val - ref_val) > 0.01:  # Допуск 0.01
                    errors['price'].append({
                        'row': i + 1,
                        'result': result_price,
                        'reference': ref_price
                    })
            except:
                if str(result_price).strip() != str(ref_price).strip():
                    errors['price'].append({
                        'row': i + 1,
                        'result': result_price,
                        'reference': ref_price
                    })

    # Сравниваем количества
    if result_keys.get('quantity') and ref_keys.get('quantity'):
        for i in range(min_len):
            result_qty = result_items[i].get(result_keys['quantity'])
            ref_qty = ref_items[i].get(ref_keys['quantity'])

            try:
                # Извлекаем число из строки (например, "1 шт" -> 1)
                result_val = float(''.join(filter(str.isdigit, str(result_qty).replace(',', '.'))) or '0')
                ref_val = float(''.join(filter(str.isdigit, str(ref_qty).replace(',', '.'))) or '0')
                if abs(result_val - ref_val) > 0.01:
                    errors['quantity'].append({
                        'row': i + 1,
                        'result': result_qty,
                        'reference': ref_qty
                    })
            except:
                if str(result_qty).strip() != str(ref_qty).strip():
                    errors['quantity'].append({
                        'row': i + 1,
                        'result': result_qty,
                        'reference': ref_qty
                    })

    # Сравниваем суммы
    if result_keys.get('amount') and ref_keys.get('amount'):
        for i in range(min_len):
            result_amt = result_items[i].get(result_keys['amount'])
            ref_amt = ref_items[i].get(ref_keys['amount'])

            try:
                result_val = float(str(result_amt).replace(',', '.').replace(' ', '').replace('"', ''))
                ref_val = float(str(ref_amt).replace(',', '.').replace(' ', '').replace('"', ''))
                if abs(result_val - ref_val) > 0.01:
                    errors['amount'].append({
                        'row': i + 1,
                        'result': result_amt,
                        'reference': ref_amt
                    })
            except:
                if str(result_amt).strip() != str(ref_amt).strip():
                    errors['amount'].append({
                        'row': i + 1,
                        'result': result_amt,
                        'reference': ref_amt
                    })

    total_errors = sum(len(errors[k]) for k in errors)

    return {
        'total_rows': min_len,
        'errors': errors,
        'total_errors': total_errors,
        'article_errors': len(errors['article']),
        'price_errors': len(errors['price']),
        'quantity_errors': len(errors['quantity']),
        'amount_errors': len(errors['amount']),
        'accuracy': (min_len * 4 - total_errors) / (min_len * 4) * 100 if min_len > 0 else 0
    }

def main():
    output_dir = Path("output")
    reference_file = Path("examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json")

    # Загружаем эталон
    with open(reference_file, 'r', encoding='utf-8') as f:
        ref_data = json.load(f)

    print("=" * 80)
    print("ПОИСК 10 ЛУЧШИХ ФАЙЛОВ ПО КАЧЕСТВУ ДАННЫХ")
    print("=" * 80)
    print(f"\n📋 Эталон: {reference_file.name}")
    print()

    # Находим все файлы dnipromash
    all_files = list(output_dir.rglob("*dnipromash*.json"))

    # Исключаем merged файлы
    all_files = [f for f in all_files if '_merged' not in f.name]

    print(f"Найдено {len(all_files)} файлов для анализа\n")

    results = []

    for f in sorted(all_files):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)

            comparison = compare_business_fields(data, ref_data)

            if 'error' in comparison:
                continue

            # Определяем промпт по имени файла или структуре
            file_str = str(f.relative_to(output_dir))
            prompt = "unknown"

            if "v6" in file_str.lower():
                prompt = "items_v6.txt"
            elif "v8" in file_str.lower() or "_v8" in file_str.lower():
                prompt = "items_v8.txt"
            elif "v9" in file_str.lower() or "_v9" in file_str.lower():
                prompt = "items_v9.txt"
            elif "0312" in file_str or "arch" in file_str:
                prompt = "items_v6.txt (arch)"
            elif "0412" in file_str:
                prompt = "items_v7.txt (вероятно)"
            elif "0512" in file_str:
                # По структуре определяем
                items = data.get('table_data', {}).get('line_items', [])
                if items:
                    cols = list(items[0].keys())
                    if 'sku' in cols:
                        prompt = "items_v8/v9.txt"
                    elif 'article_number' in cols:
                        prompt = "items_v7.txt"

            results.append({
                'file': f.relative_to(output_dir),
                'prompt': prompt,
                'comparison': comparison
            })

        except Exception as e:
            pass

    # Сортируем по общему количеству ошибок (приоритет артикулам)
    # Используем взвешенную оценку: артикулы важнее
    def score(result):
        comp = result['comparison']
        # Артикулы весят больше
        return comp['article_errors'] * 10 + comp['price_errors'] * 2 + comp['quantity_errors'] + comp['amount_errors']

    results.sort(key=score)

    print("=" * 80)
    print("ТОП-10 ЛУЧШИХ ФАЙЛОВ")
    print("=" * 80)
    print()

    for i, result in enumerate(results[:10], 1):
        comp = result['comparison']
        print(f"{i}. 📄 {result['file']}")
        print(f"   Промпт: {result['prompt']}")
        print(f"   Строк: {comp['total_rows']}")
        print(f"   Ошибки:")
        print(f"     • Артикулы: {comp['article_errors']} (критично)")
        print(f"     • Цены: {comp['price_errors']}")
        print(f"     • Количества: {comp['quantity_errors']}")
        print(f"     • Суммы: {comp['amount_errors']}")
        print(f"   Всего ошибок: {comp['total_errors']} из {comp['total_rows'] * 4} полей")
        print(f"   Точность: {comp['accuracy']:.1f}%")

        # Показываем критические ошибки в артикулах
        if comp['article_errors'] > 0:
            critical = [e for e in comp['errors']['article'] if e['row'] in [1, 8, 11]]
            if critical:
                print(f"   Критичные строки (1,8,11):")
                for err in critical[:3]:
                    print(f"     Row {err['row']}: '{err['result']}' vs '{err['reference']}'")

        print()

    # Статистика по промптам
    print("=" * 80)
    print("СТАТИСТИКА ПО ПРОМПТАМ")
    print("=" * 80)
    print()

    prompt_stats = {}
    for result in results:
        prompt = result['prompt']
        if prompt not in prompt_stats:
            prompt_stats[prompt] = {
                'count': 0,
                'total_errors': [],
                'article_errors': []
            }
        prompt_stats[prompt]['count'] += 1
        prompt_stats[prompt]['total_errors'].append(result['comparison']['total_errors'])
        prompt_stats[prompt]['article_errors'].append(result['comparison']['article_errors'])

    for prompt, stats in sorted(prompt_stats.items(), key=lambda x: sum(x[1]['article_errors']) / len(x[1]['article_errors'])):
        avg_article = sum(stats['article_errors']) / len(stats['article_errors'])
        avg_total = sum(stats['total_errors']) / len(stats['total_errors'])
        print(f"📝 {prompt}:")
        print(f"   Файлов: {stats['count']}")
        print(f"   Среднее ошибок в артикулах: {avg_article:.1f}")
        print(f"   Среднее общих ошибок: {avg_total:.1f}")
        print()

if __name__ == "__main__":
    main()






