"""
Оркестратор обработки документов
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..core.config import Config
# НЕ импортируем Pydantic модели - используем простые dict
from ..core.errors import ProcessingError, GeminiAPIError
from ..preprocessing.pdf_preprocessor import PDFPreprocessor
from ..preprocessing.image_preprocessor import ImagePreprocessor
from ..services.gemini_client import GeminiClient
from ..exporters.json_exporter import JSONExporter
from ..exporters.excel_exporter import ExcelExporter
from ..utils.file_ops import ensure_dir, get_file_hash

logger = logging.getLogger(__name__)


class Orchestrator:
    """Главный оркестратор обработки документов"""

    def __init__(self, config: Config):
        """
        Инициализация оркестратора

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.pdf_preprocessor = PDFPreprocessor(config)
        self.image_preprocessor = ImagePreprocessor(config)
        self.gemini_client = GeminiClient(config)
        self.json_exporter = JSONExporter(config)
        self.excel_exporter = ExcelExporter(config)

    def process_document(self, document_path: Path) -> Dict[str, Any]:
        """
        Обработка документа

        Args:
            document_path: Путь к документу

        Returns:
            Результат обработки

        Raises:
            ProcessingError: При ошибке обработки
        """
        logger.info(f"Starting document processing: {document_path}")

        try:
            # Проверка существования файла
            if not document_path.exists():
                raise ProcessingError(f"Document not found: {document_path}")

            # Определение типа документа
            file_extension = document_path.suffix.lower()

            # Обработка в зависимости от типа
            if file_extension == '.pdf':
                result = self._process_pdf(document_path)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                result = self._process_image(document_path)
            else:
                raise ProcessingError(f"Unsupported file format: {file_extension}")

            # Экспорт результатов
            self._export_results(document_path, result)

            logger.info(f"Document processing completed: {document_path}")

            return {
                "success": True,
                "document": str(document_path),
                "data": result,
                "processed_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to process document {document_path}: {e}", exc_info=True)
            return {
                "success": False,
                "document": str(document_path),
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }

    def _process_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Обработка PDF документа

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Распарсенные данные (dict) счета
        """
        logger.info(f"Processing PDF: {pdf_path}")

        # Препроцессинг PDF
        images = self.pdf_preprocessor.process_pdf(pdf_path)

        if not images:
            raise ProcessingError("No images extracted from PDF")

        logger.info(f"Extracted {len(images)} page(s) from PDF")

        # Обработка первой страницы (header)
        main_image = images[0]
        additional_images = images[1:] if len(images) > 1 else None

        return self._parse_with_gemini(main_image, additional_images)

    def _process_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Обработка изображения

        Args:
            image_path: Путь к изображению

        Returns:
            Распарсенные данные (dict) счета
        """
        logger.info(f"Processing image: {image_path}")

        # Препроцессинг изображения
        processed_image = self.image_preprocessor.process_image(image_path)

        logger.info(f"Image preprocessed: {processed_image}")

        return self._parse_with_gemini(processed_image)

    def _parse_with_gemini(
        self,
        main_image: Path,
        additional_images: Optional[list[Path]] = None
    ) -> Dict[str, Any]:
        """
        Парсинг документа с помощью Gemini
        
        ЛОГИКА ИЗ СТАРОГО ПРОЕКТА:
        - Возвращаем простой dict (без Pydantic!)
        - Структура как в старом gemini_parser.py
        - Используем публичный метод parse_json_response

        Args:
            main_image: Основное изображение (первая страница)
            additional_images: Дополнительные изображения

        Returns:
            Распарсенные данные в формате dict
        """
        import time
        
        logger.info("Starting Gemini parsing")

        try:
            # ЛОГИКА ИЗ СТАРОГО ПРОЕКТА: структура результата
            result = {
                "source_file": str(main_image),
                "model": self.config.gemini_model,
                "timestamp": time.time(),
                "header": {},
                "tables": [],
                "pages": []
            }

            # Парсинг header (первый запрос) 
            logger.info("Parsing header...")
            header_response = self.gemini_client.parse_with_prompt_file(
                image_path=main_image,
                prompt_file_path=self.config.prompt_header_path,
                max_tokens=None  # Используем значение из config (90000)
            )

            logger.info("Header parsed successfully")

            # Парсинг JSON из ответа (используем публичный метод!)
            header_data = self.gemini_client.parse_json_response(header_response, "header")
            
            # ЛОГИКА ИЗ СТАРОГО ПРОЕКТА: просто dict, никакого Pydantic!
            if "error" not in header_data:
                result["header"] = header_data
            else:
                logger.warning(f"Header parsing had errors: {header_data.get('error')}")

            # Парсинг items (второй запрос)
            logger.info("Parsing items...")
            items_response = self.gemini_client.parse_with_prompt_file(
                image_path=main_image,
                prompt_file_path=self.config.prompt_items_path,
                additional_images=additional_images,
                max_tokens=None  # Используем значение из config (90000)
            )

            logger.info("Items parsed successfully")

            # Парсинг JSON из ответа
            items_data = self.gemini_client.parse_json_response(items_response, "items")

            # ЛОГИКА ИЗ СТАРОГО ПРОЕКТА: извлекаем tables из результата
            if "error" in items_data:
                result["error"] = items_data["error"]
                return result

            # Новый формат промпта возвращает {"tables": [[...]], "fields": [...]}
            if "tables" in items_data and isinstance(items_data["tables"], list):
                if len(items_data["tables"]) > 0:
                    result["tables"] = items_data["tables"]
                    # Добавляем в pages
                    for i, table in enumerate(items_data["tables"]):
                        result["pages"].append({
                            "page_number": i + 1,
                            "items": table
                        })
            # Обратная совместимость со старым форматом {"items": [...]}
            elif "items" in items_data:
                result["tables"] = [items_data["items"]]
                result["pages"].append({
                    "page_number": 1,
                    "items": items_data["items"]
                })

            # Если есть fields (текстовые поля вне таблиц)
            if "fields" in items_data:
                if "header" not in result:
                    result["header"] = {}
                result["header"]["fields"] = items_data["fields"]

            logger.info(f"Parsing completed: {len(result.get('tables', [[]])[0] if result.get('tables') else 0)} items found")

            return result

        except Exception as e:
            logger.error(f"Gemini parsing failed: {e}", exc_info=True)
            raise GeminiAPIError(f"Failed to parse document with Gemini: {e}")

    def _export_results(self, document_path: Path, invoice_data: Dict[str, Any]):
        """
        Экспорт результатов

        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета
        """
        try:
            # Экспорт в JSON
            json_path = self.json_exporter.export(document_path, invoice_data)
            logger.info(f"Exported to JSON: {json_path}")

            # Экспорт в Excel отключен (только JSON)

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            # Не падаем при ошибке экспорта
