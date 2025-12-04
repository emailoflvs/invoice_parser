"""
Точка входа для Web API
"""
from ..infra.logging_setup import setup_logging
from ..core.config import Config
from ..adapters.web_api import WebAPI

if __name__ == '__main__':
    # Загрузка конфигурации
    config = Config.load()

    # Настройка логирования
    setup_logging(config.log_level, config.logs_dir)

    # Создание и запуск Web API
    api = WebAPI(config)
    api.run()
