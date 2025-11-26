"""
Точка входа для Telegram бота
"""
from ..infra.logging_setup import setup_logging
from ..adapters.telegram_bot import main

if __name__ == '__main__':
    # Настройка логирования
    setup_logging()

    # Запуск Telegram бота
    main()
