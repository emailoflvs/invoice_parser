"""
Препроцессинг изображений для улучшения качества распознавания
"""
import logging
from pathlib import Path
from typing import Optional
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

from ..core.config import Config
from ..core.errors import PreprocessingError
from ..utils.file_ops import ensure_dir

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Препроцессор для улучшения качества изображений"""

    def __init__(self, config: Config):
        """
        Инициализация препроцессора

        Args:
            config: Конфигурация приложения
        """
        self.config = config

    def process_image(self, image_path: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Обработка изображения

        Args:
            image_path: Путь к исходному изображению
            output_dir: Директория для сохранения результата (по умолчанию TEMP_DIR)

        Returns:
            Путь к обработанному изображению

        Raises:
            PreprocessingError: При ошибке обработки
        """
        logger.info(f"Processing image: {image_path}")

        try:
            # Проверка существования файла
            if not image_path.exists():
                raise PreprocessingError(f"Image not found: {image_path}")

            # Если препроцессинг отключен, возвращаем исходный путь
            if not self.config.enable_image_enhancement:
                logger.info("Image enhancement disabled, using original")
                return image_path

            # Загрузка изображения
            image = Image.open(image_path)
            logger.info(f"Loaded image: {image.size}, mode: {image.mode}")

            # Конвертация в RGB если нужно
            if image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')

            # Применение улучшений
            image = self._enhance_image(image)

            # Определение выходной директории
            if output_dir is None:
                output_dir = self.config.temp_dir

            ensure_dir(output_dir)

            # Генерация имени файла
            ext = self.config.image_format.lower()
            if ext == "jpeg":
                ext = "jpg"
            output_filename = f"preprocessed_{image_path.stem}.{ext}"
            output_path = output_dir / output_filename

            # Сохранение
            self._save_image(image, output_path)

            logger.info(f"Image preprocessed: {output_path}")

            return output_path

        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}", exc_info=True)
            raise PreprocessingError(f"Failed to process image: {e}")

    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """
        Применение улучшений к изображению

        Args:
            image: Исходное изображение

        Returns:
            Улучшенное изображение
        """
        # Upscale
        if self.config.image_upscale_factor > 1.0:
            new_size = (
                int(image.width * self.config.image_upscale_factor),
                int(image.height * self.config.image_upscale_factor)
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.debug(f"Upscaled to: {new_size}")

        # Яркость
        if self.config.image_brightness_factor != 1.0:
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(self.config.image_brightness_factor)
            logger.debug(f"Brightness adjusted: {self.config.image_brightness_factor}")

        # Контраст
        if self.config.image_contrast_factor != 1.0:
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(self.config.image_contrast_factor)
            logger.debug(f"Contrast adjusted: {self.config.image_contrast_factor}")

        # Резкость
        if self.config.image_sharpness_factor != 1.0:
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(self.config.image_sharpness_factor)
            logger.debug(f"Sharpness adjusted: {self.config.image_sharpness_factor}")

        # Цвет/Насыщенность
        if self.config.image_color_factor != 1.0 and image.mode == 'RGB':
            enhancer = ImageEnhance.Color(image)
            image = enhancer.enhance(self.config.image_color_factor)
            logger.debug(f"Color adjusted: {self.config.image_color_factor}")

        # Unsharp mask
        if self.config.image_unsharp_radius > 0:
            image = image.filter(
                ImageFilter.UnsharpMask(
                    radius=self.config.image_unsharp_radius,
                    percent=self.config.image_unsharp_percent,
                    threshold=self.config.image_unsharp_threshold
                )
            )
            logger.debug("Unsharp mask applied")

        # Шумоподавление (с использованием OpenCV)
        if self.config.image_denoise_strength > 0:
            image = self._denoise_image(image)

        # Бинаризация
        if self.config.image_binarize:
            image = self._binarize_image(image)

        # Морфологическое расширение (dilate)
        if self.config.image_dilate:
            image = self._dilate_image(image)

        return image

    def _denoise_image(self, image: Image.Image) -> Image.Image:
        """
        Шумоподавление с использованием OpenCV

        Args:
            image: Исходное изображение

        Returns:
            Изображение после шумоподавления
        """
        try:
            # Конвертация в numpy array
            img_array = np.array(image)

            # Определение силы шумоподавления
            h = int(self.config.image_denoise_strength * 30)  # 0-30 range

            # Применение Non-local Means Denoising
            if len(img_array.shape) == 3:  # RGB
                denoised = cv2.fastNlMeansDenoisingColored(img_array, None, h, h, 7, 21)
            else:  # Grayscale
                denoised = cv2.fastNlMeansDenoising(img_array, None, h, 7, 21)

            # Конвертация обратно в PIL
            return Image.fromarray(denoised)

        except Exception as e:
            logger.warning(f"Denoising failed: {e}, skipping")
            return image

    def _binarize_image(self, image: Image.Image) -> Image.Image:
        """
        Бинаризация изображения

        Args:
            image: Исходное изображение

        Returns:
            Бинаризованное изображение
        """
        try:
            # Конвертация в grayscale
            if image.mode != 'L':
                image = image.convert('L')

            # Бинаризация по порогу
            threshold = self.config.image_binarize_threshold
            image = image.point(lambda x: 255 if x > threshold else 0, mode='1')

            logger.debug(f"Image binarized with threshold: {threshold}")

            return image.convert('RGB')

        except Exception as e:
            logger.warning(f"Binarization failed: {e}, skipping")
            return image

    def _dilate_image(self, image: Image.Image) -> Image.Image:
        """
        Морфологическое расширение (dilate)

        Args:
            image: Исходное изображение

        Returns:
            Изображение после dilate
        """
        try:
            # Конвертация в numpy array
            img_array = np.array(image)

            # Создание ядра
            kernel_size = self.config.image_dilate_kernel
            kernel = np.ones((kernel_size, kernel_size), np.uint8)

            # Применение dilate
            dilated = cv2.dilate(img_array, kernel, iterations=1)

            logger.debug(f"Dilate applied with kernel size: {kernel_size}")

            return Image.fromarray(dilated)

        except Exception as e:
            logger.warning(f"Dilate failed: {e}, skipping")
            return image

    def _save_image(self, image: Image.Image, output_path: Path):
        """
        Сохранение изображения

        Args:
            image: Изображение для сохранения
            output_path: Путь для сохранения
        """
        try:
            save_kwargs = {
                'dpi': (self.config.image_dpi, self.config.image_dpi)
            }

            # Дополнительные параметры для JPEG
            if self.config.image_format.upper() == 'JPEG':
                save_kwargs['quality'] = self.config.image_quality
                save_kwargs['optimize'] = True

                # JPEG не поддерживает альфа-канал
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGB')

            # Дополнительные параметры для PNG
            elif self.config.image_format.upper() == 'PNG':
                save_kwargs['optimize'] = True

            image.save(output_path, **save_kwargs)

            logger.debug(f"Image saved: {output_path}, size: {output_path.stat().st_size} bytes")

        except Exception as e:
            raise PreprocessingError(f"Failed to save image: {e}")
