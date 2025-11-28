"""
Оркестратор обработки документов
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..core.config import Config
# НЕ импортируем Pydantic модели - используем простые dict
from ..core.errors import ProcessingError, GeminiAPIError
from ..preprocessing.pdf_preprocessor import PDFPreprocessor
from ..preprocessing.image_preprocessor import ImagePreprocessor
from ..services.gemini_client import GeminiClient
from ..services.post_processor import InvoicePostProcessor
from ..exporters.json_exporter import JSONExporter
from ..exporters.excel_exporter import ExcelExporter
from ..utils.file_ops import ensure_dir, get_file_hash

logger = logging.getLogger(__name__)


def _lazy_import_test_engine():
    """Ленивый импорт TestEngine для избежания циклических зависимостей"""
    from ..services.test_engine import TestEngine
    return TestEngine


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
        self.post_processor = InvoicePostProcessor()
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
        start_time = time.time()
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

            # Тестирование если MODE=TEST
            test_result = None
            if self.config.mode.upper() == 'TEST':
                test_result = self._run_test_for_document(document_path, result)
                # Добавляем результаты теста в данные
                result['test_results'] = test_result

            # Экспорт результатов
            output_file = self._export_results(document_path, result)

            elapsed_time = time.time() - start_time
            logger.info(f"Document processing completed: {document_path} (took {elapsed_time:.2f}s)")

            return {
                "success": True,
                "document": str(document_path),
                "data": result,
                "processed_at": datetime.now().isoformat(),
                "elapsed_time": elapsed_time,
                "test_results": test_result,
                "output_file": str(output_file) if output_file else None
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

    def _run_test_for_document(self, document_path: Path, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Запуск теста для одного документа

        Args:
            document_path: Путь к исходному документу
            parsed_data: Распарсенные данные

        Returns:
            Результаты теста
        """
        try:
            TestEngine = _lazy_import_test_engine()
            test_engine = TestEngine(self.config)

            # Ищем эталонный JSON
            expected_path = self.config.examples_dir / f"{document_path.stem}.json"

            if not expected_path.exists():
                logger.info(f"No reference file for {document_path.name} - skipping test")
                return {
                    "status": "no_reference",
                    "message": f"No reference file found: {expected_path.name}",
                    "errors": 0
                }

            # Загружаем эталон
            with open(expected_path, 'r', encoding='utf-8') as f:
                expected_data = json.load(f)

            # Нормализуем структуры
            expected_normalized = test_engine._normalize_structure(expected_data)
            actual_normalized = test_engine._normalize_structure(parsed_data)

            # 1. Сравниваем header (шапку)
            header_differences = test_engine._compare_header(expected_normalized, actual_normalized)

            # 2. Сравниваем items (товары)
            item_differences = test_engine._compare_items(
                expected_normalized.get('items', []),
                actual_normalized.get('items', [])
            )

            # Объединяем все различия
            differences = header_differences + item_differences
            error_count = len(differences)

            # Формируем краткий список ошибок для вывода (первые 5)
            sample_errors = []
            for diff in differences[:5]:
                line = diff.get('line', '?')
                path = diff.get('path', '').split('.')[-1]
                expected = diff.get('expected', 'N/A')
                actual = diff.get('actual', 'N/A')

                # Укорачиваем значения
                exp_str = str(expected)[:30] + '...' if len(str(expected)) > 30 else str(expected)
                act_str = str(actual)[:30] + '...' if len(str(actual)) > 30 else str(actual)

                # Используем технические названия как есть
                field_name = path

                sample_errors.append(f"строка {line}: {field_name}: {exp_str} vs {act_str}")

            return {
                "status": "tested",
                "reference_file": expected_path.name,
                "errors": error_count,
                "total_items": len(expected_normalized.get('items', [])),
                "sample_errors": sample_errors,
                "all_differences": differences  # Полный список для JSON
            }

        except Exception as e:
            logger.error(f"Test failed for {document_path}: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "errors": -1
            }

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

            # INFO: Логируем структуру items_data
            logger.info(f"items_data keys: {items_data.keys() if isinstance(items_data, dict) else type(items_data)}")
            if isinstance(items_data, dict) and "tables" in items_data:
                logger.info(f"tables count: {len(items_data['tables'])}")
                if items_data['tables']:
                    first_table = items_data['tables'][0]
                    logger.info(f"First table type: {type(first_table)}")
                    if isinstance(first_table, dict):
                        logger.info(f"First table keys: {first_table.keys()}")
                    elif isinstance(first_table, list):
                        logger.info(f"First table is list with {len(first_table)} items")

            # Проверка ошибок
            if "error" in header_data or "error" in items_data:
                logger.error("Parsing failed")
                if "error" in header_data:
                    logger.error(f"Header error: {header_data.get('error')}")
                if "error" in items_data:
                    logger.error(f"Items error: {items_data.get('error')}")
                return {
                    "error": "Parsing failed",
                    "header_error": header_data.get('error'),
                    "items_error": items_data.get('error')
                }

            # Если данные упакованы в header объект, распаковываем
            if "header" in header_data and isinstance(header_data["header"], dict):
                header_data = header_data["header"]

            # МАГИЯ: Post-processing через InvoicePostProcessor
            # Превращаем сырые данные Gemini в финальную структуру
            logger.info("Post-processing parsed data...")
            result = self.post_processor.process(
                {"document_info": header_data.get("document_info", {}),
                 "parties": header_data.get("parties", {}),
                 "contract_reference": header_data.get("contract_reference", {}),
                 "amounts": header_data.get("amounts", {}),
                 "other_fields": header_data.get("other_fields", {})},
                items_data
            )

            # Добавляем служебные данные
            result["_meta"] = {
                "source_file": str(main_image),
                "model": self.config.gemini_model,
                "timestamp": datetime.now().isoformat(),
                "processing_time_seconds": 0  # Будет обновлено позже
            }

            items_count = len(result.get("line_items", []))
            logger.info(f"Parsing completed: {items_count} items found")

            return result

        except Exception as e:
            logger.error(f"Gemini parsing failed: {e}", exc_info=True)
            raise GeminiAPIError(f"Failed to parse document with Gemini: {e}")


    def _export_results(self, document_path: Path, invoice_data: Dict[str, Any]) -> Optional[Path]:
        """
        Экспорт результатов

        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета (может содержать test_results)

        Returns:
            Путь к сохраненному JSON файлу
        """
        try:
            # Если есть результаты теста, добавляем их в данные перед экспортом
            if 'test_results' in invoice_data and invoice_data['test_results']:
                test_results = invoice_data['test_results']

                # Создаем копию данных для экспорта с результатами теста
                export_data = invoice_data.copy()

                # Добавляем секцию test_results в начало файла
                # Формируем полный список ошибок для JSON
                all_errors = []
                for diff in test_results.get('all_differences', []):
                    line = diff.get('line')
                    path = diff.get('path', '')
                    expected = diff.get('expected', 'N/A')
                    actual = diff.get('actual', 'N/A')
                    description = diff.get('description', '')

                    # Используем технические названия полей
                    if line is not None:
                        # Item error
                        all_errors.append({
                            "line": line,
                            "field": path.split('.')[-1],
                            "expected": str(expected),
                            "actual": str(actual)
                        })
                    else:
                        # Header error
                        all_errors.append({
                            "section": "header",
                            "field": description or path,
                            "expected": str(expected)[:100],
                            "actual": str(actual)[:100]
                        })

                export_data_with_test = {
                    "test_results": {
                        "status": test_results.get('status'),
                        "errors": test_results.get('errors', 0),
                        "reference_file": test_results.get('reference_file', 'N/A'),
                        "sample_errors": test_results.get('sample_errors', []),
                        "all_errors": all_errors  # Полный список всех ошибок
                    }
                }

                # Добавляем остальные данные
                for key, value in export_data.items():
                    if key != 'test_results':
                        export_data_with_test[key] = value

                # Экспорт в JSON с результатами теста
                json_path = self.json_exporter.export(document_path, export_data_with_test)
                logger.info(f"Exported to JSON with test results: {json_path}")
            else:
                # Экспорт в JSON без результатов теста
                json_path = self.json_exporter.export(document_path, invoice_data)
                logger.info(f"Exported to JSON: {json_path}")

            # Экспорт в Excel отключен (только JSON)
            return json_path

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            # Не падаем при ошибке экспорта
            return None
