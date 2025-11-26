"""
Оркестратор обработки документов
"""
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..core.config import Config
from ..core.models import InvoiceHeader, InvoiceData
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

    def _process_pdf(self, pdf_path: Path) -> InvoiceData:
        """
        Обработка PDF документа

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Распарсенные данные счета
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

    def _process_image(self, image_path: Path) -> InvoiceData:
        """
        Обработка изображения

        Args:
            image_path: Путь к изображению

        Returns:
            Распарсенные данные счета
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
    ) -> InvoiceData:
        """
        Парсинг документа с помощью Gemini

        Args:
            main_image: Основное изображение (первая страница)
            additional_images: Дополнительные изображения

        Returns:
            Распарсенные данные
        """
        logger.info("Starting Gemini parsing")

        try:
            # Парсинг header (первый запрос)
            header_response = self.gemini_client.parse_with_prompt_file(
                image_path=main_image,
                prompt_file_path=self.config.prompt_header_path
            )

            logger.info("Header parsed successfully")

            # Парсинг JSON из ответа
            header_data = self._extract_json(header_response)
            logger.debug(f"Header data from Gemini: {header_data}")
            
            # Маппинг полей перед созданием объекта
            if "document_date" in header_data and "date" not in header_data:
                # Преобразуем строку в date объект
                date_str = header_data.get("document_date")
                if date_str and isinstance(date_str, str):
                    for fmt in ['%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y', '%Y/%m/%d']:
                        try:
                            header_data["date"] = datetime.strptime(date_str.strip(), fmt).date()
                            break
                        except ValueError:
                            continue
                else:
                    header_data["date"] = date_str
                del header_data["document_date"]
            if "document_number" in header_data and "invoice_number" not in header_data:
                header_data["invoice_number"] = header_data.get("document_number")
            
            # Удаляем document_date, если он все еще есть
            if "document_date" in header_data:
                del header_data["document_date"]
            
            logger.debug(f"Header data after mapping: {header_data}")
            header = InvoiceHeader(**header_data)

            # Парсинг items (второй запрос) - используем больше токенов и timeout для больших списков
            items_response = self.gemini_client.parse_with_prompt_file(
                image_path=main_image,
                prompt_file_path=self.config.prompt_items_path,
                additional_images=additional_images,
                max_tokens=32768,  # Увеличенный лимит для items
                timeout=120  # Увеличенный timeout для больших документов (2 минуты)
            )

            logger.info("Items parsed successfully")

            # Парсинг JSON из ответа
            items_data = self._extract_json(items_response)

            # Преобразование формата из tables в items
            items = []
            if "tables" in items_data and items_data["tables"]:
                # Берем первую таблицу (основная таблица с товарами)
                table = items_data["tables"][0] if items_data["tables"] else []
                for idx, row in enumerate(table, start=1):
                    item = {
                        "line_number": idx,
                        "name": row.get("Найменування", row.get("Назва", row.get("Товар", ""))),
                        "sku": row.get("Артикул", row.get("Код", row.get("SKU", ""))),
                        "unit": row.get("Од. вим.", row.get("Одиниця", row.get("Од.", ""))),
                        "quantity": row.get("Кількість", row.get("К-сть", "")),
                        "price": row.get("Ціна", row.get("Цена", "")),
                        "amount": row.get("Сума", row.get("Вартість", "")),
                        "vat_rate": row.get("ПДВ", row.get("НДС", "")),
                        "vat_amount": row.get("Сума ПДВ", row.get("Сумма НДС", ""))
                    }
                    items.append(item)
            elif "items" in items_data:
                items = items_data["items"]

            # Создание результата
            invoice_data = InvoiceData(
                header=header,
                items=items
            )

            return invoice_data

        except Exception as e:
            logger.error(f"Gemini parsing failed: {e}", exc_info=True)
            raise GeminiAPIError(f"Failed to parse document with Gemini: {e}")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        Извлечение JSON из текстового ответа

        Args:
            text: Текст с JSON

        Returns:
            Распарсенный JSON

        Raises:
            ProcessingError: Если JSON не найден
        """
        # Удаление markdown форматирования
        text = text.strip()

        # Поиск JSON блока
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            json_text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            json_text = text[start:end].strip()
        else:
            json_text = text

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}\nText: {json_text[:500]}...")
            raise ProcessingError(f"Invalid JSON in response: {e}")

    def _export_results(self, document_path: Path, invoice_data: InvoiceData):
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
