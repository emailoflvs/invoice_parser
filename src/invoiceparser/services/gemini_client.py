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

    def _get_generation_config(self, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Получить конфигурацию генерации
        
        ЛОГИКА ИЗ СТАРОГО ПРОЕКТА:
        - temperature из config (по умолчанию 0)
        - max_tokens из config (по умолчанию 90000)

        Args:
            max_tokens: Переопределить max_output_tokens (если None - из config)

        Returns:
            Словарь с параметрами генерации
        """
        # Берём из config или переопределяем
        tokens = max_tokens if max_tokens is not None else self.config.image_max_output_tokens
        
        config = {
            "temperature": self.config.image_temperature,
            "top_p": self.config.image_top_p,
            "max_output_tokens": tokens,
        }

        logger.debug(f"Generation config: temperature={config['temperature']}, max_tokens={tokens}")

        return config

    def parse_document_with_vision(
        self,
        image_path: Path,
        prompt: str,
        additional_images: Optional[List[Path]] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> str:
        """
        Парсинг документа с использованием vision модели
        
        ЛОГИКА ИЗ СТАРОГО ПРОЕКТА:
        - Прямой вызов API (без threading)
        - Логирование времени выполнения

        Args:
            image_path: Путь к основному изображению
            prompt: Промпт для модели
            additional_images: Дополнительные изображения
            max_tokens: Максимальное количество токенов (если None - из config)
            timeout: Не используется (оставлен для совместимости)

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

            # Создание модели с правильными настройками из config
            model = genai.GenerativeModel(
                model_name=self.config.gemini_model,
                generation_config=self._get_generation_config(max_tokens=max_tokens)
            )

            # Формирование контента для запроса
            content = [prompt] + images

            logger.info(f"Sending request to Gemini with {len(images)} image(s)")

            # Определяем таймаут
            request_timeout = timeout if timeout is not None else self.config.gemini_timeout
            logger.info(f"Request timeout: {request_timeout}s")

            # ЛОГИКА ИЗ СТАРОГО ПРОЕКТА: Прямой вызов с таймаутом через threading
            import time
            import threading
            
            start_time = time.time()
            response = None
            exception = None
            
            def make_request():
                nonlocal response, exception
                try:
                    response = model.generate_content(content)
                except Exception as e:
                    exception = e
            
            request_thread = threading.Thread(target=make_request)
            request_thread.daemon = True
            request_thread.start()
            request_thread.join(timeout=request_timeout)
            
            if request_thread.is_alive():
                raise GeminiAPIError(f"Request timeout after {request_timeout} seconds")
            
            if exception is not None:
                raise exception
            
            if response is None:
                raise GeminiAPIError("Failed to get response from Gemini API")
            
            elapsed = time.time() - start_time
            logger.info(f"Response received in {elapsed:.2f}s")

            if not response or not response.text:
                raise GeminiAPIError("Empty response from Gemini API")

            raw_text = response.text
            logger.info(f"Received response from Gemini ({len(raw_text)} chars)")

            return raw_text

        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise GeminiAPIError(f"Failed to parse document: {e}")

    def parse_with_prompt_file(
        self,
        image_path: Path,
        prompt_file_path: Path,
        additional_images: Optional[List[Path]] = None,
        max_tokens: int = 16384,
        timeout: Optional[int] = None
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
                additional_images=additional_images,
                max_tokens=max_tokens,
                timeout=timeout
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
    
    def parse_json_response(self, raw_text: str, debug_name: str = "response") -> Dict[str, Any]:
        """
        Парсинг JSON ответа с обработкой ошибок
        
        ЛОГИКА ИЗ СТАРОГО ПРОЕКТА:
        - Правильная очистка от markdown (startswith/endswith)
        - Детальное логирование ошибок
        - Сохранение debug файла при ошибках
        
        Args:
            raw_text: Сырой ответ от Gemini
            debug_name: Имя для debug файла
            
        Returns:
            Распарсенный JSON
            
        Raises:
            GeminiAPIError: При ошибке парсинга
        """
        import json
        
        # Очистка от markdown (логика из старого проекта)
        text = raw_text.strip()
        
        if text.startswith("```json"):
            text = text[7:]  # Удаляем ```json
        if text.endswith("```"):
            text = text[:-3]  # Удаляем ```
        
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            # ЛОГИКА ИЗ СТАРОГО ПРОЕКТА: детальное логирование
            logger.error(f"JSON Decode Error at position {e.pos}: {e.msg}")
            logger.error(f"Raw text length: {len(text)} characters")
            logger.error(f"First 200 chars: {text[:200]}")
            logger.error(f"Last 200 chars: {text[-200:]}")
            
            # Сохраняем для отладки
            debug_path = Path(self.config.output_dir) / f"debug_gemini_{debug_name}.txt"
            try:
                debug_path.parent.mkdir(parents=True, exist_ok=True)
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(f"=== Original raw text ===\n{raw_text}\n\n")
                    f.write(f"=== After cleaning ===\n{text}\n")
                logger.error(f"Full response saved to: {debug_path}")
            except Exception as save_error:
                logger.error(f"Failed to save debug response: {save_error}")
            
            raise GeminiAPIError(f"Invalid JSON received from model: {e}")
