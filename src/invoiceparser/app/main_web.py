"""
Точка входа для Web API
"""
from ..infra.logging_setup import setup_logging
from ..core.config import Config
from ..adapters.web_api import WebAPI

if __name__ == '__main__':
    # Настройка логирования
    setup_logging()

    # Загрузка конфигурации
    config = Config.load()

    # Создание и запуск Web API
    api = WebAPI(config)
    api.run()
