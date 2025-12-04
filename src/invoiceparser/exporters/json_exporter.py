"""Экспорт результатов в JSON"""
import json
import logging
from decimal import Decimal
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any
from ..core.config import Config
# НЕ импортируем InvoiceData - работаем с Dict
from ..core.errors import ExportError

logger = logging.getLogger(__name__)

class JSONExporter:
    """Экспортер в JSON формат"""

    def __init__(self, config: Config):
        """
        Инициализация экспортера

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.output_dir = config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, document_path: Path, invoice_data: Dict[str, Any]) -> Path:
        """
        Экспорт данных счета в JSON

        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета (dict)

        Returns:
            Путь к созданному JSON файлу
        """
        try:
            # Генерируем имя файла: название_документа_модель_деньмесяцчасминута_количество_ошибок.json
            filename_base = document_path.stem
            now = datetime.now()
            timestamp = f"{now.day:02d}{now.month:02d}{now.hour:02d}{now.minute:02d}"
            # Нормализуем название модели для использования в имени файла
            model_name = self.config.gemini_model.replace('.', '-').replace('/', '-').replace('\\', '-')

            # Проверяем наличие результатов теста
            if 'test_results' in invoice_data and invoice_data['test_results']:
                error_count = invoice_data['test_results'].get('errors', 0)
                output_path = self.output_dir / f"{filename_base}_{model_name}_{timestamp}_{error_count}errors.json"
            else:
                output_path = self.output_dir / f"{filename_base}_{model_name}_{timestamp}.json"

            logger.debug(f"Exporting to JSON: {output_path.name}")

            # invoice_data уже dict - используем напрямую
            # Кастомный encoder для Decimal, date, datetime
            def json_encoder(obj):
                if isinstance(obj, Decimal):
                    return float(obj)
                if isinstance(obj, (date, datetime)):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

            json_data = json.dumps(invoice_data, indent=2, ensure_ascii=False, default=json_encoder)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_data)

            logger.info(f"JSON exported successfully: {output_path.name}")
            return output_path

        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}", exc_info=True)
            raise ExportError(f"Failed to export JSON: {e}") from e

# Алиас для обратной совместимости
JsonExporter = JSONExporter
