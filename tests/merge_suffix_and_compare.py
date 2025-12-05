#!/usr/bin/env python3
"""
Объединение article + article_suffix и сравнение с эталоном
"""
import json
from pathlib import Path
from typing import Dict, Any, List

def merge_suffix_files(output_dir: Path, reference_file: Path):
    """Находит файлы с suffix, объединяет article + suffix, сравнивает с эталоном"""

    # Загружаем эталон
    with open(reference_file, 'r', encoding='utf-8') as f:
        ref_data = json.load(f)

    ref_items = ref_data.get('table_data', {}).get('line_items', [])
    ref_art_key = next((k for k in ref_items[0].keys() if 'article' in k.lower()), None)

    if not ref_art_key:
        print("❌ Ключ артикула не найден в эталоне")
        return

    print("=" * 80)
    print("ОБРАБОТКА ФАЙЛОВ С SUFFIX")
    print("=" * 80)
    print(f"\n📋 Эталон: {len(ref_items)} строк, ключ: '{ref_art_key}'")
    print()

    # Находим все файлы с suffix
    all_files = list(output_dir.rglob("*dnipromash*.json"))

    files_with_suffix = []

    for f in sorted(all_files):
        try:
            with open(f, 'r', encoding='utf-8') as file:
                data = json.load(file)

            items = data.get('table_data', {}).get('line_items', [])
            if not items:
                continue

            first_row = items[0]
            cols = list(first_row.keys())

            # Ищем ключи с suffix
            suffix_key = None
            article_key = None

            for k in cols:
                k_lower = k.lower()
                if 'suffix' in k_lower or 'modifier' in k_lower:
                    suffix_key = k
                if 'article' in k_lower and 'suffix' not in k_lower and 'modifier' not in k_lower:
                    article_key = k

            if suffix_key and article_key:
                files_with_suffix.append({
                    'file': f,
                    'article_key': article_key,
                    'suffix_key': suffix_key,
                    'data': data
                })

        except Exception as e:
            pass

    print(f"✅ Найдено {len(files_with_suffix)} файлов с suffix\n")

    results = []

    for item in files_with_suffix:
        f = item['file']
        article_key = item['article_key']
        suffix_key = item['suffix_key']
        data = item['data']

        print(f"📄 {f.relative_to(output_dir)}")
        print(f"   article_key: {article_key}")
        print(f"   suffix_key: {suffix_key}")

        # Объединяем article + suffix
        items = data.get('table_data', {}).get('line_items', [])
        merged_count = 0

        for row in items:
            article_val = str(row.get(article_key, '')).strip()
            suffix_val = str(row.get(suffix_key, '')).strip()

            if suffix_val and suffix_val != '':
                # Объединяем
                merged_article = article_val + suffix_val
                row[article_key] = merged_article
                merged_count += 1
                # Удаляем suffix
                del row[suffix_key]

        # Удаляем suffix из column_mapping
        column_mapping = data.get('table_data', {}).get('column_mapping', {})
        if suffix_key in column_mapping:
            del column_mapping[suffix_key]

        print(f"   Объединено строк: {merged_count}")

        # Сохраняем обработанный файл
        processed_file = f.parent / f"{f.stem}_merged.json"
        with open(processed_file, 'w', encoding='utf-8') as out_file:
            json.dump(data, out_file, ensure_ascii=False, indent=2)

        print(f"   Сохранено: {processed_file.name}")

        # Сравниваем с эталоном
        min_len = min(len(items), len(ref_items))
        errors = []

        for i in range(min_len):
            result_art = str(items[i].get(article_key, '')).strip()
            ref_art = str(ref_items[i].get(ref_art_key, '')).strip()

            result_clean = result_art.replace(' ', '').replace('.', '').replace('-', '')
            ref_clean = ref_art.replace(' ', '').replace('.', '').replace('-', '')

            if result_clean != ref_clean:
                errors.append({
                    'row': i + 1,
                    'result': result_art,
                    'reference': ref_art
                })

        if not errors:
            print(f"   ✅ ИДЕАЛЬНО! Все {min_len} артикулов совпадают!")
            status = "PERFECT"
        else:
            print(f"   ❌ Ошибок: {len(errors)} из {min_len}")
            critical = [e for e in errors if e['row'] in [1, 8, 11]]
            if critical:
                print(f"   Критичные строки (1,8,11): {len(critical)} ошибок")
                for err in critical:
                    print(f"     Row {err['row']}: '{err['result']}' vs '{err['reference']}'")
            status = "HAS_ERRORS"

        results.append({
            'file': f.relative_to(output_dir),
            'status': status,
            'errors': len(errors),
            'total': min_len
        })

        print()

    # Итоговая сводка
    print("=" * 80)
    print("ИТОГОВАЯ СВОДКА")
    print("=" * 80)

    perfect = [r for r in results if r['status'] == 'PERFECT']
    with_errors = [r for r in results if r['status'] == 'HAS_ERRORS']

    if perfect:
        print(f"\n✅ ИДЕАЛЬНЫЕ РЕЗУЛЬТАТЫ ({len(perfect)}):")
        for r in perfect:
            print(f"   • {r['file']}")

    if with_errors:
        print(f"\n❌ РЕЗУЛЬТАТЫ С ОШИБКАМИ ({len(with_errors)}):")
        for r in sorted(with_errors, key=lambda x: x['errors']):
            print(f"   • {r['file']}: {r['errors']} ошибок из {r['total']}")

if __name__ == "__main__":
    output_dir = Path("output")
    reference_file = Path("examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json")

    merge_suffix_files(output_dir, reference_file)

