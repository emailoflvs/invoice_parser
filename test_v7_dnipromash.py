#!/usr/bin/env python3
"""
Скрипт для тестирования items_v7.txt на dnipromash 3 раза
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
logger = logging.getLogger("test_v7")

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

def main():
    """Главная функция"""
    print("=" * 60)
    print("Тестирование items_v7.txt на dnipromash (3 раза)")
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
    
    # Меняем промпт на items_v7.txt
    v7_prompt = base_dir / "prompts" / "items_v7.txt"
    if not v7_prompt.exists():
        logger.error(f"Prompt file not found: {v7_prompt}")
        sys.exit(1)
    
    config.prompt_items_path = v7_prompt
    
    logger.info(f"Using prompt: {config.prompt_items_path}")
    
    # Пути к файлам
    invoice_path = base_dir / "invoices" / "dnipromash.jpg"
    expected_path = base_dir / "examples" / "dnipromash_example.json"
    
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
    else:
        print("✗ Все тесты провалились!")
        sys.exit(1)

if __name__ == "__main__":
    main()

