#!/usr/bin/env python3
"""
Тестирование всех items промптов на dnipromash.jpg
"""
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

logging.basicConfig(level=logging.WARNING)  # Только ошибки
logger = logging.getLogger("test_all_prompts")

def test_prompt(prompt_path: Path, output_dir: Path, invoices_dir: Path, header_prompt: Path):
    """Тестирует один промпт"""
    try:
        config = Config()
        config.prompt_items_path = prompt_path
        config.prompt_header_path = header_prompt

        orchestrator = Orchestrator(config)

        invoice_file = invoices_dir / "dnipromash.jpg"
        result = orchestrator.process_document(invoice_file)

        if not result.get("success"):
            return None, result.get("error", "Unknown error")

        # Сохраняем результат
        prompt_name = prompt_path.stem
        output_name = f"dnipromash_{prompt_name}_test.json"
        output_path = output_dir / output_name

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result['data'], f, ensure_ascii=False, indent=2)

        return output_path, None

    except Exception as e:
        return None, str(e)

def compare_articles(result_file: Path, reference_file: Path) -> Dict[str, Any]:
    """Сравнивает артикулы с эталоном"""
    try:
        with open(result_file, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
        with open(reference_file, 'r', encoding='utf-8') as f:
            ref_data = json.load(f)

        result_items = result_data.get('table_data', {}).get('line_items', [])
        ref_items = ref_data.get('table_data', {}).get('line_items', [])

        if not result_items or not ref_items:
            return {'error': 'Empty items'}

        # Находим ключи артикулов
        result_art_key = None
        for k in result_items[0].keys():
            if any(x in k.lower() for x in ['article', 'sku', 'item_code']):
                result_art_key = k
                break

        ref_art_key = next((k for k in ref_items[0].keys() if 'article' in k.lower()), None)

        if not result_art_key or not ref_art_key:
            return {'error': 'Article key not found'}

        # Проверяем наличие suffix и объединяем если нужно
        suffix_key = None
        for k in result_items[0].keys():
            k_lower = k.lower()
            if ('suffix' in k_lower or 'modifier' in k_lower or 'subcode' in k_lower) and k != result_art_key:
                suffix_key = k
                break

        # Объединяем suffix если есть
        if suffix_key:
            for row in result_items:
                article_val = str(row.get(result_art_key, '')).strip()
                suffix_val = str(row.get(suffix_key, '')).strip()
                if suffix_val and suffix_val != '':
                    row[result_art_key] = article_val + suffix_val

        # Сравниваем артикулы
        min_len = min(len(result_items), len(ref_items))
        errors = []

        for i in range(min_len):
            result_art = str(result_items[i].get(result_art_key, '')).strip()
            ref_art = str(ref_items[i].get(ref_art_key, '')).strip()

            result_clean = result_art.replace(' ', '').replace('.', '').replace('-', '')
            ref_clean = ref_art.replace(' ', '').replace('.', '').replace('-', '')

            if result_clean != ref_clean:
                errors.append({
                    'row': i + 1,
                    'result': result_art,
                    'reference': ref_art
                })

        return {
            'total_rows': min_len,
            'errors_count': len(errors),
            'errors': errors,
            'has_suffix': suffix_key is not None,
            'suffix_key': suffix_key
        }

    except Exception as e:
        return {'error': str(e)}

def main():
    base_dir = Path(__file__).parent.parent
    prompts_dir = base_dir / "prompts"
    output_dir = base_dir / "output" / "prompt_tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    invoices_dir = base_dir / "invoices"
    reference_file = base_dir / "examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json"
    header_prompt = base_dir / "prompts/header_v8.txt"

    # Находим все items промпты
    items_prompts = sorted(prompts_dir.glob("items*.txt"))

    if not items_prompts:
        print("❌ No items prompts found!")
        return

    print("=" * 80)
    print(f"ТЕСТИРОВАНИЕ {len(items_prompts)} ПРОМПТОВ НА dnipromash.jpg")
    print("=" * 80)
    print()

    results = []

    for prompt_path in items_prompts:
        print(f"📄 Testing: {prompt_path.name}")

        output_file, error = test_prompt(prompt_path, output_dir, invoices_dir, header_prompt)

        if error:
            print(f"   ❌ ERROR: {error}")
            results.append({
                'prompt': prompt_path.name,
                'status': 'ERROR',
                'error': error
            })
            continue

        # Сравниваем с эталоном
        comparison = compare_articles(output_file, reference_file)

        if 'error' in comparison:
            print(f"   ⚠️  Comparison error: {comparison['error']}")
            results.append({
                'prompt': prompt_path.name,
                'status': 'COMPARE_ERROR',
                'error': comparison['error']
            })
        else:
            errors_count = comparison['errors_count']
            total = comparison['total_rows']

            if errors_count == 0:
                print(f"   ✅ PERFECT! All {total} articles match!")
                status = 'PERFECT'
            else:
                print(f"   ❌ {errors_count} errors out of {total} rows")
                critical = [e for e in comparison['errors'] if e['row'] in [1, 8, 11]]
                if critical:
                    print(f"      Critical rows (1,8,11): {len(critical)} errors")
                    for err in critical[:3]:
                        print(f"        Row {err['row']}: '{err['result']}' vs '{err['reference']}'")
                status = 'HAS_ERRORS'

            if comparison.get('has_suffix'):
                print(f"      (Used suffix field: {comparison['suffix_key']})")

            results.append({
                'prompt': prompt_path.name,
                'status': status,
                'errors_count': errors_count,
                'total_rows': total,
                'has_suffix': comparison.get('has_suffix', False)
            })

    # Итоговая сводка
    print("\n" + "=" * 80)
    print("📊 ИТОГОВАЯ СВОДКА")
    print("=" * 80)

    # Сортируем по количеству ошибок
    valid_results = [r for r in results if r['status'] in ['PERFECT', 'HAS_ERRORS']]
    valid_results.sort(key=lambda x: x.get('errors_count', 999))

    print(f"\n✅ PERFECT ({len([r for r in valid_results if r['status'] == 'PERFECT'])}):")
    for r in valid_results:
        if r['status'] == 'PERFECT':
            print(f"   • {r['prompt']}")

    print(f"\n📊 РЕЗУЛЬТАТЫ (отсортированы по ошибкам):")
    for r in valid_results:
        suffix_note = " (with suffix)" if r.get('has_suffix') else ""
        print(f"   {r['errors_count']:2d} ошибок: {r['prompt']}{suffix_note}")

    # Статистика
    if valid_results:
        best = valid_results[0]
        print(f"\n🏆 ЛУЧШИЙ РЕЗУЛЬТАТ:")
        print(f"   Промпт: {best['prompt']}")
        print(f"   Ошибок: {best['errors_count']} из {best['total_rows']} строк")
        if best.get('has_suffix'):
            print(f"   Использовал suffix для объединения")

if __name__ == "__main__":
    main()


