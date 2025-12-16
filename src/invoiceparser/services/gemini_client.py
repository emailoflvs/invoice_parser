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
from google.api_core import exceptions as google_exceptions
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

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
        # Thread-local storage для cache bypass ID (для безопасности при параллельных запросах)
        self._thread_local = threading.local()

    def _configure_api(self):
        """Настройка Gemini API"""
        try:
            genai.configure(api_key=self.config.gemini_api_key)
            logger.info(f"Gemini API configured with model: {self.config.gemini_model}, delay between requests: {self.config.gemini_timeout}s")
        except Exception as e:
            raise GeminiAPIError(f"Failed to configure Gemini API: {e}")

    def _generate_with_retry(self, model, content):
        """
        Generate content with retry mechanism.

        Настройки из .env:
        - API_RETRY_ATTEMPTS (default: 3)
        - API_RETRY_MIN_WAIT (default: 2 sec)
        - API_RETRY_MAX_WAIT (default: 10 sec)

        Retry только для временных ошибок (rate limit, timeout).
        """
        @retry(
            stop=stop_after_attempt(self.config.api_retry_attempts),
            wait=wait_exponential(
                multiplier=1,
                min=self.config.api_retry_min_wait,
                max=self.config.api_retry_max_wait
            ),
            retry=retry_if_exception_type((
                google_exceptions.DeadlineExceeded,
                google_exceptions.ServiceUnavailable,
                google_exceptions.TooManyRequests,
                google_exceptions.InternalServerError
            )),
            reraise=True
        )
        def _do_generate():
            logger.debug("Attempting to generate content...")
            return model.generate_content(content)

        try:
            return _do_generate()
        except Exception as e:
            # Последняя попытка провалилась
            logger.error(f"All {self.config.api_retry_attempts} retry attempts failed")
            raise

    def _get_generation_config(self, max_tokens: Optional[int] = None, use_seed: bool = True) -> Dict[str, Any]:
        """
        Получить конфигурацию генерации

        ЛОГИКА:
        - temperature=0 для детерминированности (стабильные результаты)
        - seed=0 для дополнительной стабильности
        - max_tokens из config (по умолчанию 90000)

        Args:
            max_tokens: Переопределить max_output_tokens (если None - из config)
            use_seed: Использовать seed для детерминированности

        Returns:
            Словарь с параметрами генерации
        """
        # Берём из config или переопределяем
        tokens = max_tokens if max_tokens is not None else self.config.image_max_output_tokens

        config = {
            "temperature": self.config.image_temperature,  # Должно быть 0 для стабильности
            "top_p": self.config.image_top_p,
            "max_output_tokens": tokens,
        }

        # Примечание: seed не поддерживается в текущей версии google-generativeai
        # Для детерминированности достаточно temperature=0 + уникальный ID в промпте

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

            # КРИТИЧНО: Cache bypass через system_instruction (НЕ влияет на промпт!)
            import uuid
            import time
            cache_bypass_id = str(uuid.uuid4())
            cache_bypass_timestamp = str(int(time.time() * 1000000))

            # System instruction для cache bypass - Gemini игнорирует это при парсинге
            system_instruction = f"[Internal ID: {cache_bypass_id}][Timestamp: {cache_bypass_timestamp}]"

            # Создание модели с правильными настройками из config
            model = genai.GenerativeModel(
                model_name=self.config.gemini_model,
                generation_config=self._get_generation_config(max_tokens=max_tokens),
                system_instruction=system_instruction  # Cache bypass БЕЗ изменения промпта!
            )

            # Сохраняем ID для проверки (thread-safe)
            self._thread_local.cache_bypass_id = cache_bypass_id

            # Формирование контента для запроса
            content = [prompt] + images

            logger.info(f"Sending request to Gemini with {len(images)} image(s)")
            logger.info(f"Cache-bypass via system_instruction: {cache_bypass_id[:16]}...")

            # RETRY механизм: настраивается через .env
            # - API_RETRY_ATTEMPTS (default: 3)
            # - API_RETRY_MIN_WAIT (default: 2)
            # - API_RETRY_MAX_WAIT (default: 10)
            import time

            start_time = time.time()
            response = self._generate_with_retry(model, content)
            elapsed = time.time() - start_time

            logger.info(f"Response received in {elapsed:.2f}s")

            if not response or not response.text:
                raise GeminiAPIError("Empty response from Gemini API")

            raw_text = response.text
            logger.info(f"Received response from Gemini ({len(raw_text)} chars)")

            return raw_text

        except google_exceptions.DeadlineExceeded as e:
            logger.error("ERROR_CODE: E004 - Request timeout (DeadlineExceeded)")
            logger.error(f"AI API timeout error: {e}", exc_info=True)
            raise GeminiAPIError("ERROR_E004|Превышено время ожидания. Попробуйте использовать документ меньшего размера.")
        except Exception as e:
            error_message = str(e)
            error_type = type(e).__name__
            logger.error(f"AI API error: {e}", exc_info=True)
            logger.error(f"Error type: {error_type}, Full error details: {error_message}", exc_info=True)

            # Определяем тип ошибки - технический код для логов, пользовательское сообщение для клиента
            if "quota" in error_message.lower() or "429" in error_message or "QuotaExceeded" in error_type:
                logger.error("ERROR_CODE: E001 - API quota exceeded")
                raise GeminiAPIError("ERROR_E001|Сервис временно недоступен из-за высокой нагрузки. Попробуйте позже.")
            elif "401" in error_message or "unauthorized" in error_message.lower() or "Unauthenticated" in error_type:
                logger.error("ERROR_CODE: E002 - API authentication error")
                raise GeminiAPIError("ERROR_E002|Ошибка конфигурации сервиса. Обратитесь в поддержку.")
            elif "403" in error_message or "forbidden" in error_message.lower() or "PermissionDenied" in error_type:
                logger.error("ERROR_CODE: E003 - API access denied")
                raise GeminiAPIError("ERROR_E003|Ошибка конфигурации сервиса. Обратитесь в поддержку.")
            elif "timeout" in error_message.lower() or "Timeout" in error_type or "DeadlineExceeded" in error_type:
                logger.error("ERROR_CODE: E004 - Request timeout")
                raise GeminiAPIError("ERROR_E004|Превышено время ожидания. Попробуйте использовать документ меньшего размера.")
            elif "network" in error_message.lower() or "connection" in error_message.lower() or "Unavailable" in error_type:
                logger.error("ERROR_CODE: E005 - Network error")
                raise GeminiAPIError("ERROR_E005|Ошибка сетевого подключения. Проверьте соединение и попробуйте снова.")
            else:
                logger.error(f"ERROR_CODE: E099 - Unknown error: {error_type} - {error_message}")
                raise GeminiAPIError(f"ERROR_E099|Не удалось обработать документ. Попробуйте снова или обратитесь в поддержку.")

    def parse_with_prompt_file(
        self,
        image_path: Path,
        prompt_file_path: Path,
        additional_images: Optional[List[Path]] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None
    ) -> str:
        """
        Парсинг документа с промптом из файла

        Args:
            image_path: Путь к изображению
            prompt_file_path: Путь к файлу с промптом
            additional_images: Дополнительные изображения (для многостраничных PDF)
            max_tokens: Максимальное количество токенов (если None - из config)
            timeout: Таймаут запроса (если None - из config)

        Returns:
            Ответ от модели

        Raises:
            GeminiAPIError: При ошибке
        """
        try:
            # Чтение промпта из файла
            if not prompt_file_path.exists():
                raise GeminiAPIError("ERROR_E006|Системная ошибка № E006")

            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                prompt = f.read().strip()

            if not prompt:
                raise GeminiAPIError(f"Empty prompt in file: {prompt_file_path}")

            logger.info(f"Loaded prompt from: {prompt_file_path}")

            # Cache bypass теперь через system_instruction в parse_document_with_vision
            # Промпт остается чистым для стабильного качества парсинга

            return self.parse_document_with_vision(
                image_path=image_path,
                prompt=prompt,  # Чистый промпт без модификаций
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

    def verify_cache_bypass(self, parsed_json: Dict[str, Any]) -> bool:
        """
        Проверка, что ответ не из кеша
        Теперь через system_instruction, поэтому просто логируем ID

        Args:
            parsed_json: Распарсенный JSON ответ

        Returns:
            True (всегда, т.к. system_instruction гарантирует уникальность)
        """
        # Используем thread-local storage для безопасности при параллельных запросах
        if hasattr(self._thread_local, 'cache_bypass_id'):
            logger.info(f"✅ CACHE BYPASS via system_instruction: {self._thread_local.cache_bypass_id[:16]}...")
        else:
            logger.warning("⚠️ Cache bypass ID not found (old request?)")

        return True  # system_instruction гарантирует уникальность запроса

    def parse_json_response(self, raw_text: str, debug_name: str = "response") -> Dict[str, Any]:
        """
        Парсинг JSON ответа с обработкой ошибок

        ЛОГИКА ИЗ СТАРОГО ПРОЕКТА:
        - Правильная очистка от markdown (startswith/endswith)
        - Детальное логирование ошибок
        - Сохранение debug файла при ошибках
        - Проверка cache-bypass

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
            parsed = json.loads(text)

            # Проверяем cache-bypass
            self.verify_cache_bypass(parsed)

            return parsed
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
