#!/usr/bin/env python3
"""
Тестирование items_v8.txt и items_v9.txt на dnipromash с эталоном v7
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

def test_prompt(prompt_name: str, config: Config):
    """Тестирование одного промпта"""
    print(f"\n{'='*60}")
    print(f"Тестирование {prompt_name} на dnipromash (сравнение с v7)")
    print(f"{'='*60}\n")

    # Используем локальные пути
    base_dir = Path(__file__).parent

    # Устанавливаем путь к промпту
    config.prompt_items_path = base_dir / "prompts" / prompt_name

    # Путь к документу
    invoice_path = base_dir / "invoices" / "dnipromash.jpg"
    if not invoice_path.exists():
        print(f"❌ Файл не найден: {invoice_path}")
        return None

    # Путь к эталону v7
    reference_path = base_dir / "examples" / "gemini_thinking_2_prompts_v7" / "dnipromash_gemini_thinking_2_prompts_v7.json"
    if not reference_path.exists():
        print(f"❌ Эталон не найден: {reference_path}")
        return None

    try:
        orchestrator = Orchestrator(config)
        result = orchestrator.process_document(invoice_path, compare_with=reference_path)

        if result.get("success"):
            test_results = result.get("data", {}).get("test_results", {})
            errors = test_results.get("errors", 0)
            print(f"✓ Ошибок: {errors}")
            return {
                "prompt": prompt_name,
                "errors": errors,
                "test_results": test_results,
                "timestamp": datetime.now().isoformat()
            }
        else:
            print(f"✗ Ошибка парсинга: {result.get('error', 'Unknown')}")
            return None

    except Exception as e:
        print(f"✗ Исключение: {e}")
        return None

def main():
    # Используем локальные пути
    base_dir = Path(__file__).parent

    # Загружаем конфиг и переопределяем пути
    config = Config.load()

    # Переопределяем пути на локальные
    config.invoices_dir = base_dir / "invoices"
    config.output_dir = base_dir / "output"
    config.examples_dir = base_dir / "examples"
    config.prompts_dir = base_dir / "prompts"
    config.temp_dir = base_dir / "temp"
    config.logs_dir = base_dir / "logs"

    results = []

    # Тестируем v8
    result_v8 = test_prompt("items_v8.txt", config)
    if result_v8:
        results.append(result_v8)

    # Тестируем v9
    result_v9 = test_prompt("items_v9.txt", config)
    if result_v9:
        results.append(result_v9)

    # Выводим итоги
    print(f"\n{'='*60}")
    print("РЕЗУЛЬТАТЫ:")
    print(f"{'='*60}")
    for r in results:
        print(f"{r['prompt']}: {r['errors']} ошибок")

    return results

if __name__ == "__main__":
    main()

