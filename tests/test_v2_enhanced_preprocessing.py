#!/usr/bin/env python3
"""
Тест items_v2.txt с улучшенной подготовкой изображения для устранения OCR ошибки
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

def test_v2_with_enhanced_preprocessing():
    """Тест items_v2.txt с улучшенной подготовкой изображения"""

    print("=" * 80)
    print("ТЕСТ: items_v2.txt с улучшенной подготовкой изображения")
    print("=" * 80)
    print()

    # Загружаем конфигурацию
    config = Config.load()

    # Переопределяем настройки препроцессинга для улучшения OCR
    # Увеличиваем контраст, резкость, upscale для лучшего распознавания цифр
    config.enable_image_enhancement = True
    config.image_upscale_factor = 2.0  # Увеличиваем в 2 раза
    config.image_brightness_factor = 1.1  # Немного увеличиваем яркость
    config.image_contrast_factor = 1.5  # Значительно увеличиваем контраст
    config.image_sharpness_factor = 2.0  # Увеличиваем резкость
    config.image_color_factor = 1.0  # Без изменений цвета
    config.image_unsharp_radius = 1.0
    config.image_unsharp_percent = 150
    config.image_unsharp_threshold = 3
    config.image_denoise_strength = 0.3  # Легкое шумоподавление
    config.image_binarize = False  # Пока без бинаризации (может ухудшить)
    config.image_binarize_threshold = 128
    config.image_dilate = False
    config.image_dpi = 300
    config.image_format = "PNG"
    config.image_quality = 95

    # Переопределяем промпт на items_v2.txt
    config.prompt_items_path = config.prompts_dir / "items_v2.txt"

    print(f"Настройки препроцессинга:")
    print(f"  • Upscale: {config.image_upscale_factor}x")
    print(f"  • Контраст: {config.image_contrast_factor}x")
    print(f"  • Резкость: {config.image_sharpness_factor}x")
    print(f"  • Яркость: {config.image_brightness_factor}x")
    print(f"  • Unsharp mask: radius={config.image_unsharp_radius}, percent={config.image_unsharp_percent}")
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
        output_file = output_dir / f"dnipromash_items_v2_enhanced_{timestamp}.json"

        parsed_data = result.get("data", {})
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(parsed_data, f, ensure_ascii=False, indent=2)

        print(f"✅ Результат сохранен: {output_file}")
        print()

        # Анализ ошибок в артикулах
        if reference_file:
            test_results = result.get("test_results", {})

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

                    # Особое внимание к строке 11 (где была ошибка 06 vs 08)
                    if err['row'] == 11:
                        print(f"    ⚠️  КРИТИЧЕСКАЯ СТРОКА 11 - проверка улучшения OCR")
            else:
                print("✅ ОШИБОК НЕТ! Улучшение препроцессинга помогло!")

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
    test_v2_with_enhanced_preprocessing()

