"""
Точка входа для Email поллера
"""
from ..infra.logging_setup import setup_logging
from ..adapters.email_poller import main

if __name__ == '__main__':
    # Настройка логирования
    setup_logging()

    # Запуск email поллера
    main()
