#!/usr/bin/env python3
"""
Автоматическое тестирование items_v2.txt с 20 различными настройками обработки изображений
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.invoiceparser.core.config import Config
from src.invoiceparser.services.orchestrator import Orchestrator
from src.invoiceparser.core.errors import ProcessingError


def load_configs() -> List[Dict[str, Any]]:
    """Загрузка конфигураций из файла"""
    configs_file = Path(__file__).parent / "image_preprocessing_configs.json"
    if not configs_file.exists():
        raise FileNotFoundError(f"Configs file not found: {configs_file}")

    with open(configs_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def apply_config_to_settings(config_obj: Config, config_dict: Dict[str, Any]) -> None:
    """Применение настроек из словаря к объекту Config"""
    config_obj.enable_image_enhancement = config_dict.get("enable_image_enhancement", True)
    config_obj.image_upscale_factor = config_dict.get("image_upscale_factor", 1.0)
    config_obj.image_brightness_factor = config_dict.get("image_brightness_factor", 1.0)
    config_obj.image_contrast_factor = config_dict.get("image_contrast_factor", 1.0)
    config_obj.image_sharpness_factor = config_dict.get("image_sharpness_factor", 1.0)
    config_obj.image_color_factor = config_dict.get("image_color_factor", 1.0)
    config_obj.image_unsharp_radius = config_dict.get("image_unsharp_radius", 0.0)
    config_obj.image_unsharp_percent = config_dict.get("image_unsharp_percent", 100)
    config_obj.image_unsharp_threshold = config_dict.get("image_unsharp_threshold", 0)
    config_obj.image_denoise_strength = config_dict.get("image_denoise_strength", 0.0)
    config_obj.image_binarize = config_dict.get("image_binarize", False)
    config_obj.image_binarize_threshold = config_dict.get("image_binarize_threshold", 128)
    config_obj.image_dilate = config_dict.get("image_dilate", False)
    config_obj.image_dilate_kernel = config_dict.get("image_dilate_kernel", 2)
    config_obj.image_dpi = config_dict.get("image_dpi", 300)
    config_obj.image_format = config_dict.get("image_format", "PNG")
    config_obj.image_quality = config_dict.get("image_quality", 95)


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


def run_single_test(config_dict: Dict[str, Any], test_file: Path, reference_file: Path,
                   output_dir: Path, test_number: int) -> Dict[str, Any]:
    """Запуск одного теста с заданной конфигурацией"""
    config_name = config_dict.get("name", f"config_{test_number:02d}")
    description = config_dict.get("description", "")

    print("=" * 80)
    print(f"ТЕСТ {test_number}/20: {config_name}")
    print(f"Описание: {description}")
    print("=" * 80)
    print()

    # Загружаем базовую конфигурацию
    config = Config.load()

    # Исправляем пути для локального запуска (если они указывают на /app)
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

    # Применяем настройки из конфигурации
    apply_config_to_settings(config, config_dict)

    # Устанавливаем промпт items_v2.txt
    config.prompt_items_path = config.prompts_dir / "items_v2.txt"

    print(f"Настройки препроцессинга:")
    print(f"  • Upscale: {config.image_upscale_factor}x")
    print(f"  • Контраст: {config.image_contrast_factor}x")
    print(f"  • Резкость: {config.image_sharpness_factor}x")
    print(f"  • Яркость: {config.image_brightness_factor}x")
    print(f"  • Бинаризация: {config.image_binarize}")
    if config.image_binarize:
        print(f"  • Порог бинаризации: {config.image_binarize_threshold}")
    print(f"  • Dilate: {config.image_dilate}")
    print(f"  • DPI: {config.image_dpi}")
    print(f"  • Формат: {config.image_format}")
    print()

    try:
        # Создаем оркестратор
        orchestrator = Orchestrator(config)

        print(f"Обработка файла: {test_file}")
        print()

        # Обрабатываем документ
        start_time = datetime.now()
        result = orchestrator.process_document(test_file, compare_with=reference_file)
        elapsed_time = (datetime.now() - start_time).total_seconds()

        # Сохраняем результат ВСЕГДА, даже при ошибках (чтобы не потерять данные от Gemini)
        timestamp = datetime.now().strftime("%m%d%H%M%S")
        output_file = output_dir / f"items_v2_{config_name}_{timestamp}.json"

        # Сохраняем полный результат, включая данные если они есть
        result_to_save = {
            "config": config_dict,
            "test_info": {
                "test_number": test_number,
                "config_name": config_name,
                "description": description,
                "timestamp": timestamp,
                "elapsed_time": elapsed_time
            },
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
                "test_number": test_number,
                "config_name": config_name,
                "description": description,
                "success": False,
                "error": error_msg,
                "elapsed_time": elapsed_time,
                "output_file": str(output_file)  # Сохраняем путь даже при ошибке
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
                for err in article_analysis['errors'][:5]:  # Показываем первые 5
                    print(f"      Row {err['row']}: '{err['result']}' vs '{err['reference']}'")
                if len(article_analysis['errors']) > 5:
                    print(f"      ... и еще {len(article_analysis['errors']) - 5} ошибок")
        else:
            print("⚠️  Эталонный файл не найден, пропускаем анализ ошибок")

        print()
        print("=" * 80)
        print()

        # Общие результаты теста
        test_results = result.get("test_results", {})

        return {
            "test_number": test_number,
            "config_name": config_name,
            "description": description,
            "success": True,
            "output_file": str(output_file),
            "elapsed_time": elapsed_time,
            "article_errors": article_analysis.get("error_count", 0),
            "total_rows": article_analysis.get("total_rows", 0),
            "critical_row_11_error": article_analysis.get("critical_row_11", False),
            "total_differences": test_results.get('total_differences', 0),
            "critical_differences": test_results.get('critical_differences', 0),
            "config": config_dict,
            "has_data": bool(parsed_data)  # Флаг наличия данных
        }

    except ProcessingError as e:
        print(f"❌ Ошибка обработки: {e}")
        return {
            "test_number": test_number,
            "config_name": config_name,
            "description": description,
            "success": False,
            "error": str(e),
            "elapsed_time": 0
        }
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()
        return {
            "test_number": test_number,
            "config_name": config_name,
            "description": description,
            "success": False,
            "error": str(e),
            "elapsed_time": 0
        }


def main():
    """Главная функция для запуска всех тестов"""
    print("=" * 80)
    print("АВТОМАТИЧЕСКОЕ ТЕСТИРОВАНИЕ items_v2.txt")
    print("20 вариантов настроек обработки изображений")
    print("=" * 80)
    print()

    # Загружаем конфигурации
    try:
        configs = load_configs()
        print(f"✅ Загружено {len(configs)} конфигураций")
    except Exception as e:
        print(f"❌ Ошибка загрузки конфигураций: {e}")
        sys.exit(1)

    # Путь к тестовому файлу
    test_file = Path("invoices/dnipromash.jpg")
    if not test_file.exists():
        print(f"❌ Файл не найден: {test_file}")
        sys.exit(1)

    # Эталонный файл
    reference_file = Path("examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json")
    if not reference_file.exists():
        print(f"⚠️  Эталонный файл не найден: {reference_file}")
        print("   Тесты будут запущены без сравнения с эталоном")
        reference_file = None

    # Создаем директорию для результатов
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Запускаем все тесты
    results = []
    start_time = datetime.now()

    for i, config_dict in enumerate(configs, 1):
        result = run_single_test(config_dict, test_file, reference_file, output_dir, i)
        results.append(result)

        # Небольшая пауза между тестами
        if i < len(configs):
            print("Пауза 2 секунды перед следующим тестом...")
            import time
            time.sleep(2)
            print()

    total_time = (datetime.now() - start_time).total_seconds()

    # Сохраняем сводный отчет
    summary_file = output_dir / f"items_v2_20_configs_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary = {
        "total_tests": len(results),
        "successful_tests": sum(1 for r in results if r.get("success")),
        "failed_tests": sum(1 for r in results if not r.get("success")),
        "total_time_seconds": total_time,
        "average_time_per_test": total_time / len(results) if results else 0,
        "best_configs": [],
        "results": results
    }

    # Находим лучшие конфигурации (с наименьшим количеством ошибок)
    successful_results = [r for r in results if r.get("success") and r.get("article_errors") is not None]
    if successful_results:
        successful_results.sort(key=lambda x: (x.get("article_errors", 999), x.get("critical_row_11_error", True)))
        summary["best_configs"] = successful_results[:5]  # Топ-5

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
    print(f"Среднее время на тест: {summary['average_time_per_test']:.1f} секунд")
    print()

    if summary["best_configs"]:
        print("ТОП-5 КОНФИГУРАЦИЙ (по количеству ошибок в артикулах):")
        for i, best in enumerate(summary["best_configs"], 1):
            print(f"  {i}. {best['config_name']} - {best.get('article_errors', 'N/A')} ошибок")
            if best.get('critical_row_11_error'):
                print(f"     ⚠️  Ошибка в строке 11")
            else:
                print(f"     ✅ Строка 11 без ошибок")

    print()
    print(f"✅ Полный отчет сохранен: {summary_file}")
    print("=" * 80)


if __name__ == "__main__":
    main()

