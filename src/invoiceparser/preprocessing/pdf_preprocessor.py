"""
Препроцессинг PDF документов
"""
import logging
from pathlib import Path
from typing import List, Optional
import fitz  # PyMuPDF
from PIL import Image

from ..core.config import Config
from ..core.errors import PreprocessingError
from ..utils.file_ops import ensure_dir
from .image_preprocessor import ImagePreprocessor

logger = logging.getLogger(__name__)


class PDFPreprocessor:
    """Препроцессор для PDF документов"""

    def __init__(self, config: Config):
        """
        Инициализация препроцессора

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.image_preprocessor = ImagePreprocessor(config)

    def process_pdf(self, pdf_path: Path) -> List[Path]:
        """
        Обработка PDF документа

        Args:
            pdf_path: Путь к PDF файлу

        Returns:
            Список путей к изображениям страниц

        Raises:
            PreprocessingError: При ошибке обработки
        """
        logger.info(f"Processing PDF: {pdf_path}")

        try:
            # Проверка существования файла
            if not pdf_path.exists():
                raise PreprocessingError(f"PDF not found: {pdf_path}")

            # Определение режима обработки
            mode = self.config.pdf_processing_mode

            if mode == "DIRECT":
                return self._process_direct(pdf_path)
            elif mode == "IMAGE_BASED":
                return self._process_image_based(pdf_path)
            elif mode == "HYBRID":
                return self._process_hybrid(pdf_path)
            else:
                raise PreprocessingError(f"Unknown PDF processing mode: {mode}")

        except Exception as e:
            logger.error(f"PDF preprocessing failed: {e}", exc_info=True)
            raise PreprocessingError(f"Failed to process PDF: {e}")

    def _process_direct(self, pdf_path: Path) -> List[Path]:
        """
        Прямая обработка PDF (без конвертации в изображения)

        Args:
            pdf_path: Путь к PDF

        Returns:
            Список с путем к исходному PDF
        """
        logger.info("Using DIRECT mode (PDF as-is)")

        # В режиме DIRECT возвращаем сам PDF
        # Gemini может работать с PDF напрямую, но мы конвертируем для единообразия
        return self._convert_to_images(pdf_path)

    def _process_image_based(self, pdf_path: Path) -> List[Path]:
        """
        Обработка через конвертацию в изображения

        Args:
            pdf_path: Путь к PDF

        Returns:
            Список путей к изображениям
        """
        logger.info("Using IMAGE_BASED mode")

        # Конвертация в изображения
        images = self._convert_to_images(pdf_path)

        # Применение image preprocessing к каждой странице
        if self.config.enable_image_enhancement:
            processed_images = []
            for img_path in images:
                processed_img = self.image_preprocessor.process_image(img_path)
                processed_images.append(processed_img)
            return processed_images

        return images

    def _process_hybrid(self, pdf_path: Path) -> List[Path]:
        """
        Гибридная обработка (выбор метода на основе содержимого)

        Args:
            pdf_path: Путь к PDF

        Returns:
            Список путей к изображениям
        """
        logger.info("Using HYBRID mode")

        # Анализ PDF
        has_text = self._has_extractable_text(pdf_path)

        if has_text:
            logger.info("PDF has extractable text, using DIRECT mode")
            return self._process_direct(pdf_path)
        else:
            logger.info("PDF is image-based, using IMAGE_BASED mode")
            return self._process_image_based(pdf_path)

    def _convert_to_images(self, pdf_path: Path) -> List[Path]:
        """
        Конвертация PDF в изображения

        Args:
            pdf_path: Путь к PDF

        Returns:
            Список путей к изображениям
        """
        logger.info(f"Converting PDF to images: {pdf_path}")

        try:
            # Открытие PDF
            doc = fitz.open(pdf_path)

            # Проверка количества страниц
            page_count = len(doc)
            logger.info(f"PDF has {page_count} page(s)")

            if page_count > self.config.pdf_max_pages:
                logger.warning(
                    f"PDF has {page_count} pages, limiting to {self.config.pdf_max_pages}"
                )
                page_count = self.config.pdf_max_pages

            # Подготовка выходной директории
            output_dir = self.config.temp_dir / f"pdf_{pdf_path.stem}"
            ensure_dir(output_dir)

            # Конвертация страниц
            image_paths = []
            matrix = fitz.Matrix(
                self.config.pdf_image_dpi / 72,
                self.config.pdf_image_dpi / 72
            )

            for page_num in range(page_count):
                page = doc[page_num]

                # Рендеринг страницы
                pix = page.get_pixmap(matrix=matrix)

                # Сохранение изображения
                output_filename = f"page_{page_num + 1:03d}.png"
                output_path = output_dir / output_filename

                pix.save(output_path)
                image_paths.append(output_path)

                logger.debug(f"Converted page {page_num + 1}/{page_count}: {output_path}")

            doc.close()

            logger.info(f"Converted {len(image_paths)} page(s) to images")

            return image_paths

        except Exception as e:
            raise PreprocessingError(f"Failed to convert PDF to images: {e}")

    def _has_extractable_text(self, pdf_path: Path) -> bool:
        """
        Проверка наличия извлекаемого текста в PDF

        Args:
            pdf_path: Путь к PDF

        Returns:
            True если есть достаточно текста
        """
        try:
            doc = fitz.open(pdf_path)

            # Проверяем первую страницу
            if len(doc) == 0:
                return False

            page = doc[0]
            text = page.get_text().strip()

            doc.close()

            # Проверяем количество символов
            has_text = len(text) >= self.config.pdf_text_threshold

            logger.debug(
                f"PDF text check: {len(text)} chars, "
                f"threshold: {self.config.pdf_text_threshold}, "
                f"has_text: {has_text}"
            )

            return has_text

        except Exception as e:
            logger.warning(f"Failed to check PDF text: {e}")
            return False

    def extract_text(self, pdf_path: Path) -> str:
        """
        Извлечение текста из PDF

        Args:
            pdf_path: Путь к PDF

        Returns:
            Извлеченный текст

        Raises:
            PreprocessingError: При ошибке извлечения
        """
        try:
            doc = fitz.open(pdf_path)

            text_parts = []
            page_count = min(len(doc), self.config.pdf_max_pages)

            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text()
                text_parts.append(f"--- Page {page_num + 1} ---\n{text}")

            doc.close()

            full_text = "\n\n".join(text_parts)

            logger.info(f"Extracted {len(full_text)} characters from PDF")

            return full_text

        except Exception as e:
            raise PreprocessingError(f"Failed to extract text from PDF: {e}")
