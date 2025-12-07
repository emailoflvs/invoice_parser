#!/usr/bin/env python3
"""
Тестирование items_v10.txt, items_v11.txt, items_v12.txt на dnipromash
По 2 раза каждый, сравнение с эталоном v7, детальные ошибки
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

def run_test(prompt_name: str, test_num: int, config: Config) -> Dict[str, Any]:
    """Запуск одного теста"""
    print(f"\n{'='*60}")
    print(f"Тест {test_num}/2: {prompt_name} на dnipromash (сравнение с v7)")
    print(f"{'='*60}\n")

    # Используем локальные пути
    base_dir = Path(__file__).parent

    # Устанавливаем пути к промптам
    config.prompt_items_path = base_dir / "prompts" / prompt_name
    # Используем header_v8.txt для всех тестов (как в v10)
    config.prompt_header_path = base_dir / "prompts" / "header_v8.txt"

    # Переопределяем пути на локальные
    config.invoices_dir = base_dir / "invoices"
    config.output_dir = base_dir / "output"
    config.examples_dir = base_dir / "examples"
    config.prompts_dir = base_dir / "prompts"
    config.temp_dir = base_dir / "temp"
    config.logs_dir = base_dir / "logs"

    # Путь к документу
    invoice_path = config.invoices_dir / "dnipromash.jpg"
    if not invoice_path.exists():
        print(f"❌ Файл не найден: {invoice_path}")
        return None

    # Путь к эталону v7
    reference_path = config.examples_dir / "gemini_thinking_2_prompts_v7" / "dnipromash_gemini_thinking_2_prompts_v7.json"
    if not reference_path.exists():
        print(f"❌ Эталон не найден: {reference_path}")
        return None

    try:
        orchestrator = Orchestrator(config)

        start_time = time.time()
        result = orchestrator.process_document(invoice_path, compare_with=reference_path)
        elapsed = time.time() - start_time

        if result.get("success"):
            test_results = result.get("data", {}).get("test_results", {})
            errors = test_results.get("errors", 0)
            all_differences = test_results.get("all_differences", [])

            print(f"✓ Ошибок: {errors} (время: {elapsed:.2f}s)\n")

            if all_differences:
                print("Детальные ошибки:")
                print("| № | Раздел | Поле | Ожидается | Получено |")
                print("|---|--------|------|-----------|----------|")
                for diff in all_differences:
                    line = diff.get("line", "header")
                    field = diff.get("field", diff.get("path", ""))
                    expected = str(diff.get("expected", ""))
                    actual = str(diff.get("actual", ""))
                    print(f"| {line} | {field} | {expected} | {actual} |")
            else:
                print("✅ Ошибок не найдено!")

            # Получаем модель из конфига
            model = config.gemini_model

            return {
                "prompt": prompt_name,
                "model": model,
                "test_num": test_num,
                "errors": errors,
                "all_errors": test_results.get("all_errors", []),
                "all_differences": all_differences,
                "test_results": test_results,
                "elapsed": elapsed,
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_msg = result.get('error', 'Unknown')
            print(f"✗ Ошибка парсинга: {error_msg}")
            return {
                "prompt": prompt_name,
                "test_num": test_num,
                "success": False,
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }

    except Exception as e:
        print(f"✗ Исключение: {e}")
        import traceback
        traceback.print_exc()
        return {
            "prompt": prompt_name,
            "test_num": test_num,
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def save_results(prompt_name: str, results: List[Dict[str, Any]], config: Config):
    """Сохранение результатов в файл"""
    base_dir = Path(__file__).parent
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)

    # Получаем модель из первого успешного результата
    model = "unknown"
    for r in results:
        if r.get("model"):
            model = r["model"]
            break

    # Формируем имя файла: dnipromash_модель_дата_время_ошибки.json
    timestamp = datetime.now().strftime("%m%d%H%M")
    errors_count = sum(r.get("errors", 0) for r in results if r.get("errors") is not None)
    filename = f"dnipromash_{model}_{timestamp}_{errors_count}errors.json"
    filepath = output_dir / filename

    # Сохраняем результаты
    output_data = {
        "prompt": prompt_name,
        "model": model,
        "tests_count": len(results),
        "total_errors": errors_count,
        "tests": results,
        "reference": "gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json"
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Результаты сохранены: {filename}")
    return filepath

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

    prompts = ["items_v11.txt", "items_v12.txt"]
    all_results = {}

    for prompt_name in prompts:
        print(f"\n{'#'*60}")
        print(f"# ТЕСТИРОВАНИЕ {prompt_name}")
        print(f"{'#'*60}")

        results = []
        for test_num in range(1, 3):
            result = run_test(prompt_name, test_num, config)
            if result:
                results.append(result)
            time.sleep(2)  # Небольшая пауза между тестами

        if results:
            all_results[prompt_name] = results
            save_results(prompt_name, results, config)

    # Итоговая сводка
    print(f"\n{'='*60}")
    print("ИТОГОВАЯ СВОДКА")
    print(f"{'='*60}\n")

    for prompt_name, results in all_results.items():
        successful = [r for r in results if r.get("errors") is not None]
        if successful:
            errors_list = [r["errors"] for r in successful]
            min_err = min(errors_list)
            max_err = max(errors_list)
            avg_err = sum(errors_list) / len(errors_list)
            print(f"{prompt_name}:")
            print(f"  Тестов: {len(successful)}/2")
            print(f"  Ошибок: {min_err}-{max_err} (среднее: {avg_err:.1f})")
        else:
            print(f"{prompt_name}: Тесты не выполнены")
        print()

    return all_results

if __name__ == "__main__":
    main()

