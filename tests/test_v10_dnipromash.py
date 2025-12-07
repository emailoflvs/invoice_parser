#!/usr/bin/env python3
"""
Скрипт для тестирования items_v10.txt на dnipromash 3 раза
"""
import sys
import os
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator
from invoiceparser.services.test_engine import TestEngine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_v10")

def run_test(config: Config, invoice_path: Path, expected_path: Path, test_num: int) -> Dict[str, Any]:
    """Запуск одного теста"""
    logger.info(f"=== Тест {test_num}/3 ===")

    try:
        orchestrator = Orchestrator(config)

        # Запуск парсинга
        start_time = time.time()
        result = orchestrator.process_document(invoice_path, compare_with=expected_path)
        elapsed = time.time() - start_time

        if not result.get("success"):
            return {
                "test_num": test_num,
                "success": False,
                "error": result.get("error", "Unknown error"),
                "elapsed": elapsed
            }

        # Извлекаем результаты теста
        test_results = result.get("test_results", {})
        errors = test_results.get("errors", 0)
        error_details = test_results.get("error_details", [])

        return {
            "test_num": test_num,
            "success": True,
            "errors": errors,
            "error_details": error_details,
            "elapsed": elapsed
        }

    except Exception as e:
        logger.error(f"Test {test_num} failed: {e}", exc_info=True)
        return {
            "test_num": test_num,
            "success": False,
            "error": str(e),
            "elapsed": 0
        }

def update_report(report_path: Path, results: List[Dict[str, Any]]):
    """Обновление отчета с результатами items_v10.txt"""

    if not report_path.exists():
        logger.warning(f"Report file not found: {report_path}")
        return

    # Читаем текущий отчет
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Извлекаем результаты
    errors_list = [r["errors"] for r in results if r.get("success")]
    if not errors_list:
        logger.error("No successful tests to report")
        return

    min_errors = min(errors_list)
    max_errors = max(errors_list)
    avg_errors = sum(errors_list) / len(errors_list)
    test_count = len(errors_list)

    # Определяем стабильность
    stability = "✓ Стабильный" if min_errors == max_errors else "▲ Нестабильный"

    # Формируем новую строку для таблицы
    new_row = f"| **items_v10.txt** | **{test_count}** | **{min_errors}** | **{max_errors}** | **{avg_errors:.1f}** | **{stability}** |"

    # Ищем место вставки (после items_v2.txt)
    lines = content.split('\n')
    insert_index = -1

    for i, line in enumerate(lines):
        if '| **items_v2.txt**' in line:
            # Вставляем после строки с items_v2.txt
            insert_index = i + 1
            break

    if insert_index > 0:
        lines.insert(insert_index, new_row)
    else:
        # Если не нашли, добавляем в конец таблицы
        for i, line in enumerate(lines):
            if '| items_v5.txt' in line:
                lines.insert(i, new_row)
                break

    # Добавляем детальную секцию
    detail_section = f"""
### 10. items_v10.txt (НОВЫЙ)

- **Тестов:** {test_count}
- **Ошибок:** {min_errors}-{max_errors} (среднее: {avg_errors:.1f})
- **Стабильность:** {stability}
- **Распределение:** {dict((err, errors_list.count(err)) for err in set(errors_list))}
"""

    # Ищем место для детальной секции (после items_v2.txt)
    detail_insert_index = -1
    for i, line in enumerate(lines):
        if '### 1. items_v2.txt' in line:
            # Ищем конец секции items_v2.txt
            for j in range(i+1, len(lines)):
                if lines[j].startswith('### ') and 'items_v2.txt' not in lines[j]:
                    detail_insert_index = j
                    break
            break

    if detail_insert_index > 0:
        lines.insert(detail_insert_index, detail_section)
    else:
        # Добавляем в конец детальной секции
        for i in range(len(lines)-1, -1, -1):
            if lines[i].startswith('## II. ДЕТАЛЬНАЯ СТАТИСТИКА'):
                # Ищем конец последней секции
                for j in range(i+1, len(lines)):
                    if lines[j].startswith('## ') or (j == len(lines)-1):
                        lines.insert(j, detail_section)
                        break
                break

    # Обновляем дату
    for i, line in enumerate(lines):
        if '**Дата обновления:**' in line:
            lines[i] = f"**Дата обновления:** {datetime.now().strftime('%d %B %Y')}"
            break

    # Записываем обновленный отчет
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"Report updated: {report_path}")

def main():
    """Главная функция"""
    print("=" * 60)
    print("Тестирование items_v10.txt на dnipromash (3 раза)")
    print("=" * 60)
    print()

    # Инициализация конфигурации
    try:
        config = Config.load()
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Исправляем пути для локального запуска (если они указывают на /app)
    base_dir = Path(__file__).parent
    if str(config.output_dir).startswith('/app'):
        config.output_dir = base_dir / "output"
    if str(config.invoices_dir).startswith('/app'):
        config.invoices_dir = base_dir / "invoices"
    if str(config.examples_dir).startswith('/app'):
        config.examples_dir = base_dir / "examples"
    if str(config.temp_dir).startswith('/app'):
        config.temp_dir = base_dir / "temp"
    if str(config.prompts_dir).startswith('/app'):
        config.prompts_dir = base_dir / "prompts"
    if str(config.prompt_header_path).startswith('/app'):
        config.prompt_header_path = base_dir / "prompts" / config.prompt_header_path.name

    # Проверяем, что промпт items_v10.txt существует
    v10_prompt = base_dir / "prompts" / "items_v10.txt"
    if not v10_prompt.exists():
        logger.error(f"Prompt file not found: {v10_prompt}")
        sys.exit(1)

    # Временно меняем промпт на items_v10.txt
    original_prompt = config.prompt_items_path
    config.prompt_items_path = v10_prompt

    logger.info(f"Using prompt: {config.prompt_items_path}")

    # Пути к файлам
    base_dir = Path(__file__).parent
    invoice_path = base_dir / "invoices" / "dnipromash.jpg"
    expected_path = base_dir / "examples" / "gemini_thinking_2_prompts_v7" / "dnipromash_gemini_thinking_2_prompts_v7.json"

    if not invoice_path.exists():
        logger.error(f"Invoice not found: {invoice_path}")
        sys.exit(1)

    if not expected_path.exists():
        logger.error(f"Expected file not found: {expected_path}")
        sys.exit(1)

    # Запускаем 3 теста
    results = []
    for i in range(1, 4):
        result = run_test(config, invoice_path, expected_path, i)
        results.append(result)

        if result.get("success"):
            print(f"✓ Тест {i}: {result['errors']} ошибок ({result['elapsed']:.2f}s)")
        else:
            print(f"✗ Тест {i}: ОШИБКА - {result.get('error', 'Unknown')}")

        # Небольшая пауза между тестами
        if i < 3:
            time.sleep(2)

    print()
    print("=" * 60)
    print("РЕЗУЛЬТАТЫ:")
    print("=" * 60)

    # Статистика
    successful = [r for r in results if r.get("success")]
    if successful:
        errors_list = [r["errors"] for r in successful]
        print(f"Успешных тестов: {len(successful)}/3")
        print(f"Ошибок: мин={min(errors_list)}, макс={max(errors_list)}, среднее={sum(errors_list)/len(errors_list):.1f}")

        # Обновляем отчет
        base_dir = Path(__file__).parent
        report_path = base_dir / "tests" / "COMPLETE_FINAL_REPORT.md"
        if report_path.exists():
            update_report(report_path, successful)
            print(f"\n✓ Отчет обновлен: {report_path}")
        else:
            print(f"\n⚠ Отчет не найден: {report_path}")
    else:
        print("✗ Все тесты провалились!")
        sys.exit(1)

if __name__ == "__main__":
    main()

