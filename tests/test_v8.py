#!/usr/bin/env python3
"""
Скрипт для тестирования промптов v8 на 5 сложных файлах
"""
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_v8")

def run_test():
    # 1. Загружаем конфиг и подменяем пути к промптам
    try:
        config = Config()
        # ПОДМЕНА ПРОМПТОВ НА v8
        config.prompt_header_path = Path(__file__).parent.parent / "prompts/header_v8.txt"
        config.prompt_items_path = Path(__file__).parent.parent / "prompts/items_v8.txt"

        logger.info(f"Using Header Prompt: {config.prompt_header_path}")
        logger.info(f"Using Items Prompt: {config.prompt_items_path}")

        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # 2. Список файлов для теста (только 3 файла)
    test_files = [
        "dnipromash.jpg",
        "lakover.jpg",
        "rostov.jpeg"
    ]

    invoices_dir = Path(config.invoices_dir)
    output_dir = Path(config.output_dir)
    examples_dir = Path(config.examples_dir) / "gemini_thinking_2_prompts_v7"

    results = []

    for filename in test_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"TESTING: {filename}")

        file_path = invoices_dir / filename
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            continue

        # Ищем эталон
        ref_file = next(examples_dir.glob(f"{file_path.stem}*.json"), None)
        if ref_file:
            logger.info(f"Reference: {ref_file.name}")

        # Запуск парсинга
        try:
            result = orchestrator.process_document(file_path)

            if not result.get("success"):
                logger.error(f"Failed: {result.get('error')}")
                continue

            # Сохраняем результат с пометкой v8
            output_name = f"{file_path.stem}_v8_test.json"
            output_path = output_dir / output_name

            # Пересохраняем, чтобы имя было красивое
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result['data'], f, ensure_ascii=False, indent=2)

            logger.info(f"Saved to: {output_name}")

            results.append({
                'file': filename,
                'output': output_path,
                'reference': ref_file
            })

        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")

    logger.info("\n✅ Test completed. Check output folder.")

if __name__ == "__main__":
    run_test()


