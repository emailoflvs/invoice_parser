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

def test_prompt(prompt_path: Path, output_dir: Path, invoices_dir: Path):
    """Тестирует один промпт"""
    try:
        config = Config()
        config.prompt_items_path = prompt_path
        config.prompt_header_path = base_dir / "prompts/header_v8.txt"  # Используем v8 для header

        orchestrator = Orchestrator(config)

        invoice_file = invoices_dir / "dnipromash.jpg"
        result = orchestrator.process_document(invoice_file)

        if not result.get("success"):
            return None, result.get("error", "Unknown error")

        # Сохраняем результат
        output_name = f"dnipromash_{prompt_path.stem}.json"
        output_path = output_dir / output_name

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result['data'], f, ensure_ascii=False, indent=2)

        return output_path, None

    except Exception as e:
        return None, str(e)

def compare_with_reference(result_file: Path, reference_file: Path) -> Dict[str, Any]:
    """Сравнивает результат с эталоном, фокусируясь на артикулах"""
    try:
        with open(result_file, 'r') as f:
            result_data = json.load(f)
        with open(reference_file, 'r') as f:
            ref_data = json.load(f)

        result_items = result_data.get('table_data', {}).get('line_items', [])
        ref_items = ref_data.get('table_data', {}).get('line_items', [])

        if not result_items or not ref_items:
            return {'error': 'Empty items'}

        # Находим ключ артикула в результате
        result_art_key = None
        for k in result_items[0].keys():
            if any(x in k.lower() for x in ['article', 'sku', 'item_code', 'product_code']):
                result_art_key = k
                break

        # Находим ключ артикула в эталоне
        ref_art_key = None
        for k in ref_items[0].keys():
            if any(x in k.lower() for x in ['article', 'sku', 'item_code', 'product_code']):
                ref_art_key = k
                break

        if not result_art_key or not ref_art_key:
            return {'error': 'Article key not found'}

        # Сравниваем артикулы
        min_len = min(len(result_items), len(ref_items))
        errors = []
        perfect = True

        for i in range(min_len):
            result_art = str(result_items[i].get(result_art_key, '')).strip()
            ref_art = str(ref_items[i].get(ref_art_key, '')).strip()

            # Нормализация для сравнения
            result_clean = result_art.replace(' ', '').replace('.', '').replace('-', '').replace('/', '')
            ref_clean = ref_art.replace(' ', '').replace('.', '').replace('-', '').replace('/', '')

            if result_clean != ref_clean:
                perfect = False
                errors.append({
                    'row': i + 1,
                    'result': result_art,
                    'reference': ref_art
                })

        return {
            'perfect': perfect,
            'total_rows': min_len,
            'errors_count': len(errors),
            'errors': errors[:5]  # Первые 5 ошибок
        }

    except Exception as e:
        return {'error': str(e)}

def main():
    base_dir = Path(__file__).parent.parent
    prompts_dir = base_dir / "prompts"
    output_dir = base_dir / "output/prompt_tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    invoices_dir = base_dir / "invoices"
    reference_file = base_dir / "examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json"

    # Находим все items промпты
    items_prompts = sorted(prompts_dir.glob("items*.txt"))

    if not items_prompts:
        print("❌ No items prompts found!")
        return

    print(f"🔍 Testing {len(items_prompts)} prompts on dnipromash.jpg\n")
    print("=" * 80)

    results = []

    for prompt_path in items_prompts:
        print(f"\n📄 Testing: {prompt_path.name}")

        output_file, error = test_prompt(prompt_path, output_dir, invoices_dir)

        if error:
            print(f"   ❌ ERROR: {error}")
            results.append({
                'prompt': prompt_path.name,
                'status': 'ERROR',
                'error': error
            })
            continue

        # Сравниваем с эталоном
        comparison = compare_with_reference(output_file, reference_file)

        if 'error' in comparison:
            print(f"   ⚠️  Comparison error: {comparison['error']}")
            results.append({
                'prompt': prompt_path.name,
                'status': 'COMPARE_ERROR',
                'error': comparison['error']
            })
        elif comparison['perfect']:
            print(f"   ✅ PERFECT! All {comparison['total_rows']} articles match!")
            results.append({
                'prompt': prompt_path.name,
                'status': 'PERFECT',
                'total_rows': comparison['total_rows']
            })
        else:
            print(f"   ❌ {comparison['errors_count']} errors out of {comparison['total_rows']} rows")
            for err in comparison['errors']:
                print(f"      Row {err['row']}: '{err['result']}' vs '{err['reference']}'")
            results.append({
                'prompt': prompt_path.name,
                'status': 'HAS_ERRORS',
                'errors_count': comparison['errors_count'],
                'total_rows': comparison['total_rows'],
                'errors': comparison['errors']
            })

    # Итоговая сводка
    print("\n" + "=" * 80)
    print("📊 SUMMARY:")
    print("=" * 80)

    perfect_prompts = [r for r in results if r['status'] == 'PERFECT']
    error_prompts = [r for r in results if r['status'] == 'HAS_ERRORS']

    if perfect_prompts:
        print(f"\n✅ PERFECT PROMPTS ({len(perfect_prompts)}):")
        for r in perfect_prompts:
            print(f"   • {r['prompt']}")

    if error_prompts:
        print(f"\n❌ PROMPTS WITH ERRORS ({len(error_prompts)}):")
        for r in sorted(error_prompts, key=lambda x: x.get('errors_count', 999)):
            print(f"   • {r['prompt']}: {r['errors_count']} errors")

if __name__ == "__main__":
    main()

