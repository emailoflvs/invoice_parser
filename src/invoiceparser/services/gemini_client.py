"""
Клиент для работы с Gemini API
"""
import os
import random
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import google.generativeai as genai
from PIL import Image

from ..core.config import Config
from ..core.errors import GeminiAPIError

logger = logging.getLogger(__name__)


class GeminiClient:
    """Клиент для взаимодействия с Gemini API"""

    def __init__(self, config: Config):
        """
        Инициализация клиента

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self._configure_api()

    def _configure_api(self):
        """Настройка Gemini API"""
        try:
            genai.configure(api_key=self.config.gemini_api_key)
            logger.info(f"Gemini API configured with model: {self.config.gemini_model}, timeout: {self.config.gemini_timeout}s")
        except Exception as e:
            raise GeminiAPIError(f"Failed to configure Gemini API: {e}")

    def _get_generation_config(self) -> Dict[str, Any]:
        """
        Получить конфигурацию генерации

        Returns:
            Словарь с параметрами генерации
        """
        seed = None
        if self.config.vision_seed != "random":
            try:
                seed = int(self.config.vision_seed)
            except ValueError:
                logger.warning(f"Invalid VISION_SEED: {self.config.vision_seed}, using random")
                seed = random.randint(1, 1000000)
        else:
            seed = random.randint(1, 1000000)

        config = {
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
        }

        if seed is not None:
            logger.info(f"Using seed: {seed}")

        return config

    def parse_document_with_vision(
        self,
        image_path: Path,
        prompt: str,
        additional_images: Optional[List[Path]] = None
    ) -> str:
        """
        Парсинг документа с использованием vision модели

        Args:
            image_path: Путь к основному изображению
            prompt: Промпт для модели
            additional_images: Дополнительные изображения (для многостраничных документов)

        Returns:
            Ответ от модели

        Raises:
            GeminiAPIError: При ошибке обращения к API
        """
        try:
            # Загрузка изображений
            images = []

            # Основное изображение
            if not image_path.exists():
                raise GeminiAPIError(f"Image not found: {image_path}")

            main_image = Image.open(image_path)
            images.append(main_image)
            logger.info(f"Loaded main image: {image_path}")

            # Дополнительные изображения
            if additional_images:
                for img_path in additional_images:
                    if img_path.exists():
                        img = Image.open(img_path)
                        images.append(img)
                        logger.info(f"Loaded additional image: {img_path}")

            # Создание модели
            model = genai.GenerativeModel(
                model_name=self.config.gemini_model,
                generation_config=self._get_generation_config()
            )

            # Формирование контента для запроса
            content = [prompt] + images

            logger.info(f"Sending request to Gemini with {len(images)} image(s)")

            # Отправка запроса (timeout обрабатывается на уровне библиотеки)
            # В версии 0.3.2 request_options не поддерживается,
            # используем дефолтный timeout библиотеки
            response = model.generate_content(content)

            if not response or not response.text:
                raise GeminiAPIError("Empty response from Gemini API")

            logger.info(f"Received response from Gemini ({len(response.text)} chars)")

            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise GeminiAPIError(f"Failed to parse document: {e}")

    def parse_with_prompt_file(
        self,
        image_path: Path,
        prompt_file_path: Path,
        additional_images: Optional[List[Path]] = None
    ) -> str:
        """
        Парсинг документа с промптом из файла

        Args:
            image_path: Путь к изображению
            prompt_file_path: Путь к файлу с промптом
            additional_images: Дополнительные изображения

        Returns:
            Ответ от модели

        Raises:
            GeminiAPIError: При ошибке
        """
        try:
            # Чтение промпта из файла
            if not prompt_file_path.exists():
                raise GeminiAPIError(f"Prompt file not found: {prompt_file_path}")

            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt = f.read().strip()

            if not prompt:
                raise GeminiAPIError(f"Empty prompt in file: {prompt_file_path}")

            logger.info(f"Loaded prompt from: {prompt_file_path}")

            return self.parse_document_with_vision(
                image_path=image_path,
                prompt=prompt,
                additional_images=additional_images
            )

        except GeminiAPIError:
            raise
        except Exception as e:
            raise GeminiAPIError(f"Failed to parse with prompt file: {e}")

    def test_connection(self) -> bool:
        """
        Проверка подключения к Gemini API

        Returns:
            True если подключение успешно
        """
        try:
            model = genai.GenerativeModel(model_name=self.config.gemini_model)
            response = model.generate_content("Hello")
            return bool(response and response.text)
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
