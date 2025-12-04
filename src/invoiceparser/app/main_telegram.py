"""
Точка входа для Telegram бота
"""
from ..infra.logging_setup import setup_logging
from ..core.config import Config
from ..adapters.telegram_bot import main

if __name__ == '__main__':
    # Загрузка конфигурации
    config = Config.load()

    # Настройка логирования
    setup_logging(config.log_level, config.logs_dir)

    # Запуск Telegram бота
    main()
