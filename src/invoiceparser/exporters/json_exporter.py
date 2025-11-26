"""Экспорт результатов в JSON"""
import json
import logging
from pathlib import Path
from ..core.config import Config
from ..core.models import InvoiceData
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
    
    def export(self, document_path: Path, invoice_data: InvoiceData) -> Path:
        """
        Экспорт данных счета в JSON
        
        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета
            
        Returns:
            Путь к созданному JSON файлу
        """
        try:
            # Генерируем имя файла на основе исходного документа
            filename_base = document_path.stem
            output_path = self.output_dir / f"{filename_base}.json"
            
            logger.debug(f"Exporting to JSON: {output_path.name}")
            
            # Конвертируем в словарь и экспортируем
            json_data = invoice_data.model_dump_json(indent=2, ensure_ascii=False, exclude_none=False)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_data)
                
            logger.info(f"JSON exported successfully: {output_path.name}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error exporting to JSON: {e}", exc_info=True)
            raise ExportError(f"Failed to export JSON: {e}") from e

# Алиас для обратной совместимости
JsonExporter = JSONExporter
