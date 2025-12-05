#!/usr/bin/env python3
"""
Тестирование промпта items_v9.txt на dnipromash.jpg
"""
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_v9")

def main():
    try:
        config = Config()
        config.prompt_items_path = Path(__file__).parent.parent / "prompts/items_v9.txt"
        config.prompt_header_path = Path(__file__).parent.parent / "prompts/header_v8.txt"

        logger.info(f"Using Items Prompt: {config.prompt_items_path}")
        logger.info(f"Using Header Prompt: {config.prompt_header_path}")

        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    base_dir = Path(__file__).parent.parent
    invoice_file = Path(config.invoices_dir) / "dnipromash.jpg"
    reference_file = Path(config.examples_dir) / "gemini_thinking_2_prompts_v7" / "dnipromash_gemini_thinking_2_prompts_v7.json"
    output_dir = Path(config.output_dir)

    logger.info(f"Processing: {invoice_file.name}")

    result = orchestrator.process_document(invoice_file)

    if not result.get("success"):
        logger.error(f"Failed: {result.get('error')}")
        sys.exit(1)

    # Сохраняем результат
    output_name = "dnipromash_v9_test.json"
    output_path = output_dir / output_name

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result['data'], f, ensure_ascii=False, indent=2)

    logger.info(f"Saved to: {output_name}")

    # Сравнение с эталоном
    if reference_file.exists():
        logger.info("Comparing with reference...")

        with open(output_path, 'r', encoding='utf-8') as f:
            result_data = json.load(f)
        with open(reference_file, 'r', encoding='utf-8') as f:
            ref_data = json.load(f)

        result_items = result_data.get('table_data', {}).get('line_items', [])
        ref_items = ref_data.get('table_data', {}).get('line_items', [])

        if not result_items or not ref_items:
            logger.warning("Empty items in result or reference")
            return

        # Находим ключи артикулов
        result_art_key = next((k for k in result_items[0].keys() if any(x in k.lower() for x in ['article', 'sku', 'item_code'])), None)
        ref_art_key = next((k for k in ref_items[0].keys() if any(x in k.lower() for x in ['article', 'sku', 'item_code'])), None)

        if not result_art_key or not ref_art_key:
            logger.warning("Article key not found")
            return

        print("\n" + "=" * 80)
        print("СРАВНЕНИЕ С ЭТАЛОНОМ (v7 thinking)")
        print("=" * 80)

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

        if not errors:
            print(f"\n✅ PERFECT MATCH! All {min_len} articles match!")
        else:
            print(f"\n❌ Found {len(errors)} errors out of {min_len} rows:")
            for err in errors:
                print(f"   Row {err['row']}: '{err['result']}' vs '{err['reference']}'")

            # Проверяем критичные строки (1, 8, 11)
            critical = [e for e in errors if e['row'] in [1, 8, 11]]
            if critical:
                print(f"\n🔴 Критичные строки (1, 8, 11): {len(critical)} ошибок")
            else:
                print(f"\n✅ Критичные строки (1, 8, 11): OK!")

if __name__ == "__main__":
    main()

