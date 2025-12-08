"""Экспорт результатов в JSON"""
import json
import logging
import re
from decimal import Decimal
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any, Optional
from ..core.config import Config
# НЕ импортируем InvoiceData - работаем с Dict
from ..core.errors import ExportError

logger = logging.getLogger(__name__)


def transliterate_to_latin(text: str) -> str:
    """
    Транслитерация кириллицы в латиницу для использования в именах файлов

    Args:
        text: Текст с кириллицей

    Returns:
        Текст в латинице
    """
    # Простая таблица транслитерации для украинского/русского
    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Sch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g',
        'І': 'I', 'Ї': 'Yi', 'Є': 'Ye', 'Ґ': 'G'
    }

    result = []
    for char in text:
        if char in translit_map:
            result.append(translit_map[char])
        elif char.isalnum() or char in ['-', '_', '.']:
            result.append(char)
        else:
            result.append('_')

    # Убираем множественные подчеркивания и заменяем на одно
    result_str = ''.join(result)
    result_str = re.sub(r'_+', '_', result_str)
    result_str = result_str.strip('_')

    return result_str

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

    def export(self, document_path: Path, invoice_data: Dict[str, Any], original_filename: Optional[str] = None) -> Path:
        """
        Экспорт данных счета в JSON

        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета (dict)
            original_filename: Оригинальное имя файла (если отличается от document_path)

        Returns:
            Путь к созданному JSON файлу
        """
        try:
            # Используем оригинальное имя файла, если оно передано, иначе берем из document_path
            if original_filename:
                filename_base = Path(original_filename).stem
            else:
                filename_base = document_path.stem

            # Транслитерируем в латиницу
            filename_base = transliterate_to_latin(filename_base)

            now = datetime.now()
            timestamp = f"{now.day:02d}{now.month:02d}{now.hour:02d}{now.minute:02d}"

            # Используем модель gemini (как указано в требованиях)
            model_name = "gemini"

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
