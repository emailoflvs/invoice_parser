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

    def process_document(
        self,
        document_path: Path,
        compare_with: Optional[Path] = None,
        original_filename: Optional[str] = None,
        mode: str = "detailed"  # НОВОЕ: "fast" или "detailed"
    ) -> Dict[str, Any]:
        """
        Обработка документа

        Args:
            document_path: Путь к документу
            compare_with: Опциональный путь к эталонному JSON файлу для сравнения
            original_filename: Оригинальное имя файла (для генерации имени выходного файла)
            mode: Режим обработки - "fast" (быстрый) или "detailed" (детальный)

        Returns:
            Результат обработки

        Raises:
            ProcessingError: При ошибке обработки
        """
        start_time = time.time()
        logger.info(f"Starting document processing: {document_path} (mode: {mode})")

        try:
            # Проверка существования файла
            if not document_path.exists():
                raise ProcessingError(f"Document not found: {document_path}")

            # Определение типа документа
            file_extension = document_path.suffix.lower()

            # Обработка в зависимости от типа
            if file_extension == '.pdf':
                result = self._process_pdf(document_path, mode=mode)
            elif file_extension in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
                result = self._process_image(document_path, mode=mode)
            else:
                raise ProcessingError(f"Unsupported file format: {file_extension}")

            # Тестирование только если MODE=TEST
            test_result = None
            if self.config.mode.upper() == 'TEST':
                test_result = self._run_test_for_document(document_path, result, compare_with)
                # Добавляем результаты теста в данные
                result['test_results'] = test_result

            # Экспорт результатов
            output_file = self._export_results(document_path, result, original_filename)

            elapsed_time = time.time() - start_time
            logger.info(f"Document processing completed: {document_path} (took {elapsed_time:.2f}s)")

            return {
                "success": True,
                "document": str(document_path),
                "data": result,
                "processed_at": datetime.now().isoformat(),
                "elapsed_time": elapsed_time,
                "test_results": test_result,
                "output_file": str(output_file) if output_file else None,
                "mode": mode  # НОВОЕ: включаем режим в ответ
            }

        except Exception as e:
            logger.error(f"Failed to process document {document_path}: {e}", exc_info=True)
            return {
                "success": False,
                "document": str(document_path),
                "error": str(e),
                "processed_at": datetime.now().isoformat()
            }

    def _process_pdf(self, pdf_path: Path, mode: str = "detailed") -> Dict[str, Any]:
        """
        Обработка PDF документа

        Args:
            pdf_path: Путь к PDF файлу
            mode: Режим обработки - "fast" или "detailed"

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

        if mode == "fast":
            return self._fast_parse_with_gemini(main_image, additional_images)
        else:
            return self._parse_with_gemini(main_image, additional_images)

    def _process_image(self, image_path: Path, mode: str = "detailed") -> Dict[str, Any]:
        """
        Обработка изображения

        Args:
            image_path: Путь к изображению
            mode: Режим обработки - "fast" или "detailed"

        Returns:
            Распарсенные данные (dict) счета
        """
        logger.info(f"Processing image: {image_path}")

        # Препроцессинг изображения
        processed_image = self.image_preprocessor.process_image(image_path)

        logger.info(f"Image preprocessed: {processed_image}")

        if mode == "fast":
            return self._fast_parse_with_gemini(processed_image)
        else:
            return self._parse_with_gemini(processed_image)

    def _fast_parse_with_gemini(
        self,
        main_image: Path,
        additional_images: Optional[list[Path]] = None
    ) -> Dict[str, Any]:
        """
        БЫСТРЫЙ парсинг документа с помощью Gemini (один запрос)

        Использует быструю модель (GEMINI_MODEL_FAST) и комбинированный промпт (PROMPT_ITEMS_HEADER)

        Args:
            main_image: Основное изображение (первая страница)
            additional_images: Дополнительные изображения

        Returns:
            Распарсенные данные в формате dict
        """
        import time

        logger.info(f"Starting FAST Gemini parsing with model: {self.config.gemini_model_fast}, max_tokens: {self.config.image_max_output_tokens_fast} (optimized for speed)")

        try:
            # Временно переключаем модель на быструю
            original_model = self.config.gemini_model
            self.config.gemini_model = self.config.gemini_model_fast

            # Пересоздаем клиент с новой моделью
            self.gemini_client = GeminiClient(self.config)

            start = time.time()
            logger.info("Parsing with combined prompt (header+items)...")

            # Для быстрого режима используем меньше токенов из конфига для ускорения
            fast_max_tokens = self.config.image_max_output_tokens_fast

            response = self.gemini_client.parse_with_prompt_file(
                image_path=main_image,
                prompt_file_path=self.config.prompt_items_header,  # Комбинированный промпт
                additional_images=additional_images,
                max_tokens=fast_max_tokens  # Используем значение из IMAGE_MAX_OUTPUT_TOKENS_FAST
            )

            elapsed = time.time() - start
            logger.info(f"Fast parsing completed successfully in {elapsed:.2f}s")
            logger.info(f"FAST mode: 1 request with {self.config.gemini_model_fast}, max_tokens={self.config.image_max_output_tokens_fast}, time: {elapsed:.2f}s")

            # Парсим JSON ответ
            result = self.gemini_client.parse_json_response(response, "fast_combined")

            # Проверка ошибок
            if "error" in result:
                logger.error("Fast parsing failed")
                logger.error(f"Error: {result.get('error')}")
                return {
                    "error": "Fast parsing failed",
                    "details": result.get('error')
                }

            # Нормализуем структуру fast режима, чтобы она соответствовала detailed режиму
            # 1. Нормализуем parties: если это массив, преобразуем в объект с ключами-ролями
            if "parties" in result and isinstance(result["parties"], list):
                parties_obj = {}
                for party in result["parties"]:
                    if isinstance(party, dict) and "role" in party:
                        role = party["role"]
                        # Используем role как ключ, остальные поля как значение
                        party_data = {k: v for k, v in party.items() if k != "role"}
                        parties_obj[role] = party_data
                if parties_obj:
                    result["parties"] = parties_obj

            # 2. Извлекаем column_mapping и line_items в table_data (как в detailed режиме)
            table_data = {}
            if "column_mapping" in result:
                table_data["column_mapping"] = result["column_mapping"]
            if "line_items" in result:
                table_data["line_items"] = result["line_items"]
            elif "items" in result:
                table_data["line_items"] = result["items"]

            # Если table_data не пустой, добавляем его в результат
            if table_data:
                result["table_data"] = table_data

            # Применяем нормализацию чисел через post_processor (как в detailed режиме)
            if "totals" in result and isinstance(result["totals"], dict):
                self.post_processor._normalize_totals(result["totals"])

            if "table_data" in result and "line_items" in result["table_data"]:
                self.post_processor._normalize_line_items(result["table_data"]["line_items"])

            # Добавляем служебные данные
            result["_meta"] = {
                "source_file": str(main_image),
                "timestamp": datetime.now().isoformat(),
                "processing_time_seconds": elapsed,
                "mode": "fast",
                "model": self.config.gemini_model_fast
            }

            logger.info(f"Fast parsing completed: {len(result.get('table_data', {}).get('line_items', result.get('line_items', [])))} items found")

            # Возвращаем модель обратно
            self.config.gemini_model = original_model
            self.gemini_client = GeminiClient(self.config)

            return result

        except GeminiAPIError:
            # Пробрасываем ошибки от Gemini API как есть
            # Возвращаем модель обратно
            self.config.gemini_model = original_model
            self.gemini_client = GeminiClient(self.config)
            raise
        except Exception as e:
            logger.error(f"Fast parsing failed: {e}", exc_info=True)
            # Возвращаем модель обратно
            self.config.gemini_model = original_model
            self.gemini_client = GeminiClient(self.config)
            # Для других ошибок возвращаем общее сообщение
            raise GeminiAPIError(f"ERROR_E001|Сервис временно недоступен из-за высокой нагрузки. Попробуйте позже.")

    def _run_test_for_document(self, document_path: Path, parsed_data: Dict[str, Any], compare_with: Optional[Path] = None) -> Dict[str, Any]:
        """
        Запуск теста для одного документа

        Args:
            document_path: Путь к исходному документу
            parsed_data: Распарсенные данные
            compare_with: Опциональный путь к эталонному JSON файлу

        Returns:
            Результаты теста
        """
        try:
            TestEngine = _lazy_import_test_engine()
            test_engine = TestEngine(self.config)

            # Определяем путь к эталонному JSON
            if compare_with is not None:
                # Используем явно указанный путь
                expected_path = Path(compare_with)
            else:
                # Ищем автоматически по имени файла
                expected_path = self.config.examples_dir / f"{document_path.stem}.json"

            if not expected_path.exists():
                logger.info(f"No reference file for {document_path.name} - skipping test")
                return {
                    "status": "no_reference",
                    "message": f"No reference file found: {expected_path}",
                    "errors": 0
                }

            # Загружаем эталон
            with open(expected_path, 'r', encoding='utf-8') as f:
                expected_data = json.load(f)

            # Нормализуем структуры
            from ..services.test_engine import normalize_structure
            expected_normalized = normalize_structure(expected_data)
            actual_normalized = normalize_structure(parsed_data)

            # Сравниваем
            differences = test_engine.compare_documents(expected_normalized, actual_normalized)

            # Формируем отчёт
            error_count = len(differences)

            # Создаем список первых 10 ошибок для краткого вывода
            sample_errors = []
            all_errors = []
            for i, diff in enumerate(differences[:10]):
                line = diff.get('line')
                path = diff.get('path', '')
                expected = diff.get('expected', 'N/A')
                actual = diff.get('actual', 'N/A')
                description = diff.get('description', '')

                error_text = f"Line {line}, {path}: expected '{expected}', got '{actual}'" if line is not None else f"{description}: expected '{expected}', got '{actual}'"
                sample_errors.append(error_text)

            # Полный список ошибок
            for diff in differences:
                line = diff.get('line')
                path = diff.get('path', '')
                expected = diff.get('expected', 'N/A')
                actual = diff.get('actual', 'N/A')
                description = diff.get('description', '')

                error_text = f"Line {line}, {path}: expected '{expected}', got '{actual}'" if line is not None else f"{description}: expected '{expected}', got '{actual}'"
                all_errors.append(error_text)

            return {
                "status": "passed" if error_count == 0 else "failed",
                "reference_file": str(expected_path),
                "reference_file_name": expected_path.name,
                "errors": error_count,
                "total_items": len(expected_normalized.get('items', [])),
                "sample_errors": sample_errors,  # Первые 10 для краткого вывода
                "all_errors": all_errors,  # Все ошибки в текстовом формате
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

        Поддерживает два режима:
        - PARALLEL (по умолчанию): header и items парсятся одновременно
        - SEQUENTIAL: header парсится первым, затем items

        Args:
            main_image: Основное изображение (первая страница)
            additional_images: Дополнительные изображения

        Returns:
            Распарсенные данные в формате dict
        """
        import time
        from concurrent.futures import ThreadPoolExecutor

        mode = "PARALLEL" if self.config.parallel_parsing else "SEQUENTIAL"
        logger.info(f"Starting Gemini parsing ({mode} mode)")

        try:
            # Функция для парсинга header
            def parse_header():
                logger.info("Parsing header...")
                start = time.time()
                response = self.gemini_client.parse_with_prompt_file(
                    image_path=main_image,
                    prompt_file_path=self.config.prompt_header_path,
                    max_tokens=None  # Используем значение из config (90000)
                )
                elapsed = time.time() - start
                logger.info(f"Header parsed successfully in {elapsed:.2f}s")
                return self.gemini_client.parse_json_response(response, "header")

            # Функция для парсинга items
            def parse_items():
                logger.info("Parsing items...")
                start = time.time()
                response = self.gemini_client.parse_with_prompt_file(
                    image_path=main_image,
                    prompt_file_path=self.config.prompt_items_path,
                    additional_images=additional_images,
                    max_tokens=None  # Используем значение из config (90000)
                )
                elapsed = time.time() - start
                logger.info(f"Items parsed successfully in {elapsed:.2f}s")
                return self.gemini_client.parse_json_response(response, "items")

            # Выбор режима выполнения
            total_start = time.time()

            if self.config.parallel_parsing:
                # ПАРАЛЛЕЛЬНОЕ выполнение обоих запросов
                with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
                    # Запускаем оба запроса одновременно
                    header_future = executor.submit(parse_header)
                    items_future = executor.submit(parse_items)

                    # Ожидаем завершения обоих
                    header_data = header_future.result()
                    items_data = items_future.result()
            else:
                # ПОСЛЕДОВАТЕЛЬНОЕ выполнение
                header_data = parse_header()
                items_data = parse_items()

            total_elapsed = time.time() - total_start
            logger.info(f"Parsing completed in {total_elapsed:.2f}s ({mode} mode)")
            logger.info(f"DETAILED mode: 2 parallel requests with {self.config.gemini_model}, total time: {total_elapsed:.2f}s")

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
                logger.info(f"Unpacking header data. Original keys: {list(header_data.keys())}")
                header_data = header_data["header"]
                logger.info(f"Unpacked header keys: {list(header_data.keys())}")

            # Логируем все ключи header_data перед post-processing
            logger.info(f"Header data keys before post-processing: {list(header_data.keys())}")

            # Post-processing: передаем данные как есть
            logger.info("Post-processing parsed data...")
            result = self.post_processor.process(header_data, items_data)

            # Логируем все ключи результата после post-processing
            logger.info(f"Result keys after post-processing: {list(result.keys())}")

            # Добавляем служебные данные (без упоминания модели для клиента)
            result["_meta"] = {
                "source_file": str(main_image),
                "timestamp": datetime.now().isoformat(),
                "processing_time_seconds": 0  # Будет обновлено позже
            }

            # Динамически ищем items для логирования
            items_count = 0
            for key, value in result.items():
                if isinstance(value, list) and len(value) > 0:
                    # Если это список dict - вероятно это items
                    if isinstance(value[0], dict):
                        items_count = len(value)
                        break

            logger.info(f"Parsing completed: {items_count} items found")

            return result

        except GeminiAPIError:
            # Пробрасываем ошибки от Gemini API как есть
            raise
        except Exception as e:
            logger.error(f"Document processing failed: {e}", exc_info=True)
            # Для других ошибок возвращаем общее сообщение
            raise GeminiAPIError(f"ERROR_E001|Сервис временно недоступен из-за высокой нагрузки. Попробуйте позже.")


    def _export_results(self, document_path: Path, invoice_data: Dict[str, Any], original_filename: Optional[str] = None) -> Optional[Path]:
        """
        Экспорт результатов

        Args:
            document_path: Путь к исходному документу
            invoice_data: Данные счета (может содержать test_results)
            original_filename: Оригинальное имя файла (для генерации имени выходного файла)

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
                json_path = self.json_exporter.export(document_path, export_data_with_test, original_filename)
                logger.info(f"Exported to JSON with test results: {json_path}")
            else:
                # Экспорт в JSON без результатов теста
                json_path = self.json_exporter.export(document_path, invoice_data, original_filename)
                logger.info(f"Exported to JSON: {json_path}")

            # Экспорт в Excel отключен (только JSON)
            return json_path

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            # Не падаем при ошибке экспорта
            return None
