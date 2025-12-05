#!/usr/bin/env python3
"""
Тест items_v2.txt с обычными настройками препроцессинга (без изменений)
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.invoiceparser.core.config import Config
from src.invoiceparser.services.orchestrator import Orchestrator
from src.invoiceparser.core.errors import ProcessingError

def test_v2_normal():
    """Тест items_v2.txt с обычными настройками"""

    print("=" * 80)
    print("ТЕСТ: items_v2.txt с обычными настройками препроцессинга")
    print("=" * 80)
    print()

    # Загружаем конфигурацию (без изменений настроек)
    config = Config.load()

    # Только переопределяем промпт на items_v2.txt
    config.prompt_items_path = config.prompts_dir / "items_v2.txt"

    print(f"Используются настройки из .env:")
    print(f"  • Image enhancement: {config.enable_image_enhancement}")
    if config.enable_image_enhancement:
        print(f"  • Upscale: {config.image_upscale_factor}x")
        print(f"  • Контраст: {config.image_contrast_factor}x")
        print(f"  • Резкость: {config.image_sharpness_factor}x")
    print(f"  • Промпт: {config.prompt_items_path.name}")
    print()

    # Путь к тестовому файлу
    test_file = Path("invoices/dnipromash.jpg")
    if not test_file.exists():
        print(f"❌ Файл не найден: {test_file}")
        return

    # Эталонный файл
    reference_file = Path("examples/gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json")
    if not reference_file.exists():
        print(f"⚠️  Эталонный файл не найден: {reference_file}")
        reference_file = None

    # Создаем оркестратор
    orchestrator = Orchestrator(config)

    print(f"Обработка файла: {test_file}")
    print()

    try:
        # Обрабатываем документ
        result = orchestrator.process_document(test_file, compare_with=reference_file)

        if not result.get("success"):
            print(f"❌ Ошибка обработки: {result.get('error')}")
            return

        # Сохраняем результат
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%m%d%H%M%S")
        output_file = output_dir / f"dnipromash_items_v2_normal_{timestamp}.json"

        parsed_data = result.get("data", {})
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Результат сохранен: {output_file}")
        print()

        # Анализ ошибок в артикулах
        if reference_file:
            print("=" * 80)
            print("АНАЛИЗ ОШИБОК В АРТИКУЛАХ")
            print("=" * 80)
            print()

            # Загружаем эталон
            with open(reference_file, 'r', encoding='utf-8') as f:
                ref_data = json.load(f)

            ref_items = ref_data.get('table_data', {}).get('line_items', [])
            result_items = parsed_data.get('table_data', {}).get('line_items', [])

            if not result_items:
                print("❌ Не найдены строки в результате")
                return

            # Находим ключ артикула
            ref_art_key = 'article'
            result_art_key = None

            for k in result_items[0].keys():
                k_lower = k.lower()
                if ('article' in k_lower or 'sku' in k_lower) and 'suffix' not in k_lower:
                    result_art_key = k
                    break

            if not result_art_key:
                print("❌ Не найден ключ артикула в результате")
                return

            # Проверяем наличие suffix
            suffix_key = None
            for k in result_items[0].keys():
                k_lower = k.lower()
                if ('suffix' in k_lower or 'modifier' in k_lower) and k != result_art_key:
                    suffix_key = k
                    break

            # Объединяем suffix если есть
            if suffix_key:
                print(f"⚠️  Найден suffix ключ: {suffix_key}, объединяем с article")
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

            print(f"Всего строк: {min_len}")
            print(f"Ошибок в артикулах: {len(errors)}")
            print()

            if errors:
                print("Детали ошибок:")
                for err in errors:
                    print(f"  Row {err['row']}: '{err['result']}' vs '{err['reference']}'")

                    # Особое внимание к строке 11
                    if err['row'] == 11:
                        print(f"    ⚠️  КРИТИЧЕСКАЯ СТРОКА 11")
            else:
                print("✅ ОШИБОК НЕТ!")

            print()
            print("=" * 80)

        # Показываем общие результаты теста
        if result.get("test_results"):
            test_results = result["test_results"]
            print("Общие результаты теста:")
            print(f"  • Всего различий: {test_results.get('total_differences', 0)}")
            print(f"  • Критичных различий: {test_results.get('critical_differences', 0)}")
            print()

    except ProcessingError as e:
        print(f"❌ Ошибка обработки: {e}")
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_v2_normal()

