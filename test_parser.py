#!/usr/bin/env python3
"""
Тестовый скрипт для парсинга накладных через Gemini
"""
import sys
import os
import json
import time
import logging
from pathlib import Path

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_parser")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_parser.py <image_path>")
        sys.exit(1)
    
    image_path = Path(sys.argv[1])
    
    if not image_path.exists():
        logger.error(f"Image not found: {image_path}")
        sys.exit(1)
    
    print(f"🔍 Parsing: {image_path.name}")
    print()
    
    # Инициализация
    try:
        config = Config()
        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Запуск парсинга
    start_time = time.time()
    logger.info("Starting parsing...")
    
    result = orchestrator.process_document(image_path)
    
    elapsed = time.time() - start_time
    
    # Проверка результата
    if not result.get("success"):
        logger.error(f"Parsing failed: {result.get('error', 'Unknown error')}")
        sys.exit(1)
    
    # Извлекаем данные
    data = result.get("data", {})
    
    # Извлекаем items
    parsed_items = []
    if data.get('tables') and len(data['tables']) > 0:
        parsed_items = data['tables'][0]
    
    items_count = len(parsed_items)
    
    # Сохранение результата
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / f"{image_path.stem}_result.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Вывод результата
    print()
    print(f"✅ Success!")
    print(f"⏱️  Time: {elapsed:.2f}s")
    print(f"📦 Items found: {items_count}")
    print(f"💾 Saved to: {output_path}")
    print()
    
    # Показываем первые 3 товара
    if parsed_items:
        print("📋 First 3 items:")
        for i, item in enumerate(parsed_items[:3], 1):
            # Получаем первые 3 ключа
            keys = list(item.keys())[:3]
            item_preview = {k: item[k] for k in keys if k in item}
            print(f"  {i}. {item_preview}")

if __name__ == "__main__":
    main()
