#!/usr/bin/env python3
"""
Дополнительное тестирование промптов
"""
import sys
import json
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("additional_tests")

def test_prompt(prompt_path: Path, output_dir: Path, invoices_dir: Path, header_prompt: Path, test_num: int):
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
        output_name = f"dnipromash_{prompt_name}_test{test_num}.json"
        output_path = output_dir / output_name

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result['data'], f, ensure_ascii=False, indent=2)

        return output_path, None

    except Exception as e:
        return None, str(e)

def main():
    base_dir = Path(__file__).parent.parent
    prompts_dir = base_dir / "prompts"
    output_dir = base_dir / "output" / "prompt_tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    invoices_dir = base_dir / "invoices"
    header_prompt = base_dir / "prompts/header_v8.txt"

    # План тестирования
    test_plan = {
        'items_v2': 3,
        'items_v3': 3,
        'items_v4': 3,
        'items_v5': 2,
        'items_v9': 3,
        'items': 3
    }

    print("=" * 80)
    print("ДОПОЛНИТЕЛЬНОЕ ТЕСТИРОВАНИЕ ПРОМПТОВ")
    print("=" * 80)
    print()

    total_tests = sum(test_plan.values())
    print(f"Всего тестов: {total_tests}\n")

    for prompt_name, count in test_plan.items():
        prompt_path = prompts_dir / f"{prompt_name}.txt"

        if not prompt_path.exists():
            print(f"⚠️  Промпт {prompt_name}.txt не найден, пропускаю")
            continue

        print(f"📄 Тестирование {prompt_name}.txt ({count} раз(а)):")

        for i in range(1, count + 1):
            print(f"   Тест {i}/{count}...", end=" ", flush=True)

            output_file, error = test_prompt(prompt_path, output_dir, invoices_dir, header_prompt, i)

            if error:
                print(f"❌ ERROR: {error}")
            else:
                print(f"✅ Сохранено: {output_file.name}")

            # Небольшая задержка между тестами
            if i < count:
                time.sleep(2)

        print()

    print("=" * 80)
    print("✅ Все тесты завершены!")
    print("=" * 80)

if __name__ == "__main__":
    main()

