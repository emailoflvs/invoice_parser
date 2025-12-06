#!/usr/bin/env python3
"""
Дополнительные тесты для items_v3.txt и items_v4.txt
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import time

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.invoiceparser.core.config import Config
from src.invoiceparser.services.orchestrator import Orchestrator
from src.invoiceparser.core.errors import ProcessingError


def analyze_article_errors(parsed_data: Dict[str, Any], reference_file: Path) -> Dict[str, Any]:
    """Анализ ошибок в артикулах"""
    try:
        with open(reference_file, 'r', encoding='utf-8') as f:
            ref_data = json.load(f)

        ref_items = ref_data.get('table_data', {}).get('line_items', [])
        result_items = parsed_data.get('table_data', {}).get('line_items', [])

        if not result_items:
            return {
                "total_rows": 0,
                "errors": [],
                "error_count": 0,
                "error": "Не найдены строки в результате"
            }

        # Находим ключ артикула
        ref_art_key = 'article'
        result_art_key = None

        for k in result_items[0].keys():
            k_lower = k.lower()
            if ('article' in k_lower or 'sku' in k_lower) and 'suffix' not in k_lower:
                result_art_key = k
                break

        if not result_art_key:
            return {
                "total_rows": len(result_items),
                "errors": [],
                "error_count": 0,
                "error": "Не найден ключ артикула в результате"
            }

        # Проверяем наличие suffix
        suffix_key = None
        for k in result_items[0].keys():
            k_lower = k.lower()
            if ('suffix' in k_lower or 'modifier' in k_lower) and k != result_art_key:
                suffix_key = k
                break

        # Объединяем suffix если есть
        if suffix_key:
            for row in result_items:
                article_val = str(row.get(result_art_key, '')).strip()
                suffix_val = str(row.get(suffix_key, '')).strip()
                if suffix_val:
                    row[result_art_key] = article_val + suffix_val

        # Сравниваем
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
            "total_rows": min_len,
            "errors": errors,
            "error_count": len(errors),
            "critical_row_11": any(err['row'] == 11 for err in errors)
        }
    except Exception as e:
        return {
            "total_rows": 0,
            "errors": [],
            "error_count": 0,
            "error": str(e)
        }


def run_single_test(prompt_name: str, test_number: int, total_tests: int, output_dir: Path,
                   test_file: Path, reference_file: Path) -> Dict[str, Any]:
    """Запуск одного теста"""
    print("=" * 80)
    print(f"ТЕСТ {test_number}/{total_tests}: {prompt_name}")
    print("=" * 80)
    print()

    # Загружаем базовую конфигурацию
    config = Config.load()

    # Исправляем пути для локального запуска
    project_root = Path(__file__).parent.parent
    if str(config.output_dir).startswith('/app'):
        config.output_dir = project_root / "output"
    if str(config.temp_dir).startswith('/app'):
        config.temp_dir = project_root / "temp"
    if str(config.logs_dir).startswith('/app'):
        config.logs_dir = project_root / "logs"
    if str(config.invoices_dir).startswith('/app'):
        config.invoices_dir = project_root / "invoices"
    if str(config.examples_dir).startswith('/app'):
        config.examples_dir = project_root / "examples"
    if str(config.prompts_dir).startswith('/app'):
        config.prompts_dir = project_root / "prompts"

    # Исправляем пути к промптам
    if str(config.prompt_header_path).startswith('/app'):
        config.prompt_header_path = config.prompts_dir / config.prompt_header_path.name
    if str(config.prompt_items_path).startswith('/app'):
        config.prompt_items_path = config.prompts_dir / config.prompt_items_path.name

    # Устанавливаем нужный промпт
    config.prompt_items_path = config.prompts_dir / prompt_name

    print(f"Промпт: {prompt_name}")
    print(f"Обработка файла: {test_file}")
    print()

    try:
        # Создаем оркестратор
        orchestrator = Orchestrator(config)

        # Обрабатываем документ
        start_time = datetime.now()
        result = orchestrator.process_document(test_file, compare_with=reference_file)
        elapsed_time = (datetime.now() - start_time).total_seconds()

        # Сохраняем результат ВСЕГДА
        timestamp = datetime.now().strftime("%m%d%H%M%S")
        output_file = output_dir / f"{prompt_name.replace('.txt', '')}_test{test_number}_{timestamp}.json"

        result_to_save = {
            "prompt": prompt_name,
            "test_number": test_number,
            "timestamp": timestamp,
            "elapsed_time": elapsed_time,
            "result": result
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_to_save, f, ensure_ascii=False, indent=2)

        if not result.get("success"):
            error_msg = result.get('error', 'Unknown error')
            print(f"❌ Ошибка обработки: {error_msg}")
            print(f"⚠️  Частичный результат сохранен: {output_file}")
            print()
            return {
                "prompt": prompt_name,
                "test_number": test_number,
                "success": False,
                "error": error_msg,
                "elapsed_time": elapsed_time,
                "output_file": str(output_file)
            }

        parsed_data = result.get("data", {})
        print(f"✅ Результат сохранен: {output_file}")
        print()

        # Анализ ошибок в артикулах
        article_analysis = {}
        if reference_file and reference_file.exists():
            article_analysis = analyze_article_errors(parsed_data, reference_file)

            print("АНАЛИЗ ОШИБОК В АРТИКУЛАХ:")
            print(f"  • Всего строк: {article_analysis.get('total_rows', 0)}")
            print(f"  • Ошибок: {article_analysis.get('error_count', 0)}")

            if article_analysis.get('critical_row_11'):
                print(f"  • ⚠️  КРИТИЧЕСКАЯ СТРОКА 11 - ошибка присутствует")

            if article_analysis.get('errors'):
                print("  • Детали ошибок:")
                for err in article_analysis['errors'][:5]:
                    print(f"      Row {err['row']}: '{err['result']}' vs '{err['reference']}'")
                if len(article_analysis['errors']) > 5:
                    print(f"      ... и еще {len(article_analysis['errors']) - 5} ошибок")
        else:
            print("⚠️  Эталонный файл не найден, пропускаем анализ ошибок")

        print()
        print("=" * 80)
        print()

        return {
            "prompt": prompt_name,
            "test_number": test_number,
            "success": True,
            "output_file": str(output_file),
            "elapsed_time": elapsed_time,
            "article_errors": article_analysis.get("error_count", 0),
            "total_rows": article_analysis.get("total_rows", 0),
            "critical_row_11_error": article_analysis.get("critical_row_11", False)
        }

    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {
            "prompt": prompt_name,
            "test_number": test_number,
            "success": False,
            "error": str(e),
            "elapsed_time": 0
        }


def main():
    """Главная функция"""
    print("=" * 80)
    print("ДОПОЛНИТЕЛЬНЫЕ ТЕСТЫ ДЛЯ items_v3.txt И items_v4.txt")
    print("=" * 80)
    print()

    # Путь к тестовому файлу
    test_file = Path("invoices/dnipromash.jpg")
    if not test_file.exists():
        print(f"❌ Файл не найден: {test_file}")
        sys.exit(1)

    # Эталонный файл
    reference_file = Path("examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json")
    if not reference_file.exists():
        print(f"⚠️  Эталонный файл не найден: {reference_file}")
        reference_file = None

    # Создаем директорию для результатов
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Планируем тесты
    tests_plan = [
        ("items_v3.txt", 3),  # 3 теста для items_v3.txt
        ("items_v4.txt", 1),  # 1 тест для items_v4.txt
    ]

    # Запускаем тесты
    results = []
    start_time = datetime.now()

    for prompt_name, num_tests in tests_plan:
        print(f"\n{'='*80}")
        print(f"ТЕСТИРОВАНИЕ: {prompt_name} ({num_tests} тест(ов))")
        print(f"{'='*80}\n")

        for i in range(1, num_tests + 1):
            result = run_single_test(prompt_name, i, num_tests, output_dir, test_file, reference_file)
            results.append(result)

            # Пауза между тестами
            if i < num_tests or (prompt_name == "items_v3.txt" and num_tests == 3):
                print("Пауза 2 секунды перед следующим тестом...")
                time.sleep(2)
                print()

    total_time = (datetime.now() - start_time).total_seconds()

    # Сохраняем сводный отчет
    summary_file = output_dir / f"additional_tests_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary = {
        "total_tests": len(results),
        "successful_tests": sum(1 for r in results if r.get("success")),
        "failed_tests": sum(1 for r in results if not r.get("success")),
        "total_time_seconds": total_time,
        "results_by_prompt": {},
        "results": results
    }

    # Группируем по промптам
    for result in results:
        prompt = result.get("prompt", "unknown")
        if prompt not in summary["results_by_prompt"]:
            summary["results_by_prompt"][prompt] = {
                "tests": [],
                "error_counts": []
            }
        summary["results_by_prompt"][prompt]["tests"].append(result)
        if result.get("success") and result.get("article_errors") is not None:
            summary["results_by_prompt"][prompt]["error_counts"].append(result.get("article_errors", 0))

    # Добавляем статистику по промптам
    for prompt, data in summary["results_by_prompt"].items():
        error_counts = data["error_counts"]
        if error_counts:
            data["min_errors"] = min(error_counts)
            data["max_errors"] = max(error_counts)
            data["avg_errors"] = sum(error_counts) / len(error_counts)
            data["distribution"] = {}
            for err in error_counts:
                data["distribution"][err] = data["distribution"].get(err, 0) + 1

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Выводим итоговую сводку
    print("=" * 80)
    print("ИТОГОВАЯ СВОДКА")
    print("=" * 80)
    print(f"Всего тестов: {summary['total_tests']}")
    print(f"Успешных: {summary['successful_tests']}")
    print(f"Провалившихся: {summary['failed_tests']}")
    print(f"Общее время: {total_time:.1f} секунд ({total_time/60:.1f} минут)")
    print()

    for prompt, data in summary["results_by_prompt"].items():
        print(f"{prompt}:")
        if "min_errors" in data:
            print(f"  • Ошибок: {data['min_errors']}-{data['max_errors']} (среднее: {data['avg_errors']:.1f})")
            print(f"  • Распределение: {data['distribution']}")
        print()

    print(f"✅ Полный отчет сохранен: {summary_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

