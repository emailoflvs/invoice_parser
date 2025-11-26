"""
Точка входа для CLI приложения
"""
import sys
from ..infra.logging_setup import setup_logging
from ..adapters.cli_app import main
from ..core.config import Config

if __name__ == '__main__':
    # Загрузка конфигурации
    config = Config.load()
    
    # Настройка логирования
    setup_logging(config.log_level, config.logs_dir)

    # Запуск CLI приложения
    main()
