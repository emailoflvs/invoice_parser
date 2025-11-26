"""Настройка логирования"""
import logging
import sys
from pathlib import Path
from datetime import datetime

def setup_logging(log_level: str, logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_filename = logs_dir / f"invoiceparser_{datetime.now().strftime('%Y%m%d')}.log"
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_filename, encoding="utf-8", mode="a"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Level: {log_level}, File: {log_filename}")
