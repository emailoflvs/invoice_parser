"""Конфигурация приложения - загружается из .env"""
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Конфигурация приложения"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Основные настройки
    mode: Literal["NORMAL", "TEST"] = Field(alias="MODE")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(alias="LOG_LEVEL")
    dev_mode: bool = Field(alias="DEV_MODE", default=False)  # Режим разработки (auto-reload)
    parallel_parsing: bool = Field(alias="PARALLEL_PARSING", default=True)  # True = параллельно, False = последовательно
    parallel_workers: int = Field(alias="PARALLEL_WORKERS", default=2)  # количество параллельных потоков

    # Директории
    invoices_dir: Path = Field(alias="INVOICES_DIR")
    output_dir: Path = Field(alias="OUTPUT_DIR")
    logs_dir: Path = Field(alias="LOGS_DIR")
    temp_dir: Path = Field(alias="TEMP_DIR")
    examples_dir: Path = Field(alias="EXAMPLES_DIR")

    # Gemini API
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(alias="GEMINI_MODEL")
    gemini_model_fast: str = Field(alias="GEMINI_MODEL_FAST", default="gemini-2.0-flash-exp")
    gemini_timeout: int = Field(alias="GEMINI_TIMEOUT")
    # vision_seed больше не используется - timestamp генерируется динамически
    prompts_dir: Path = Field(alias="PROMPTS_DIR")
    prompt_header_path: Path = Field(alias="PROMPT_HEADER_PATH")
    prompt_items_path: Path = Field(alias="PROMPT_ITEMS_PATH")
    prompt_items_header: Path = Field(alias="PROMPT_ITEMS_HEADER", default=Path("prompts/header+items.txt"))

    # Настройки изображений
    enable_image_enhancement: bool = Field(alias="ENABLE_IMAGE_ENHANCEMENT")
    image_upscale_factor: float = Field(alias="IMAGE_UPSCALE_FACTOR")
    image_brightness_factor: float = Field(alias="IMAGE_BRIGHTNESS_FACTOR")
    image_contrast_factor: float = Field(alias="IMAGE_CONTRAST_FACTOR")
    image_sharpness_factor: float = Field(alias="IMAGE_SHARPNESS_FACTOR")
    image_color_factor: float = Field(alias="IMAGE_COLOR_FACTOR")
    image_unsharp_radius: float = Field(alias="IMAGE_UNSHARP_RADIUS")
    image_unsharp_percent: int = Field(alias="IMAGE_UNSHARP_PERCENT")
    image_unsharp_threshold: int = Field(alias="IMAGE_UNSHARP_THRESHOLD")
    image_denoise_strength: float = Field(alias="IMAGE_DENOISE_STRENGTH")
    image_binarize: bool = Field(alias="IMAGE_BINARIZE")
    image_binarize_threshold: int = Field(alias="IMAGE_BINARIZE_THRESHOLD")
    image_dilate: bool = Field(alias="IMAGE_DILATE")
    image_dilate_kernel: int = Field(alias="IMAGE_DILATE_KERNEL")
    image_dpi: int = Field(alias="IMAGE_DPI")
    image_format: Literal["PNG", "JPEG"] = Field(alias="IMAGE_FORMAT")
    image_quality: int = Field(alias="IMAGE_QUALITY")
    image_temperature: float = Field(alias="IMAGE_TEMPERATURE")
    image_top_p: float = Field(alias="IMAGE_TOP_P")
    image_max_output_tokens: int = Field(alias="IMAGE_MAX_OUTPUT_TOKENS")
    image_max_output_tokens_fast: int = Field(alias="IMAGE_MAX_OUTPUT_TOKENS_FAST", default=4096)

    # Настройки PDF
    pdf_processing_mode: Literal["DIRECT", "IMAGE_BASED", "HYBRID"] = Field(alias="PDF_PROCESSING_MODE")
    pdf_image_dpi: int = Field(alias="PDF_IMAGE_DPI")
    pdf_max_pages: int = Field(alias="PDF_MAX_PAGES")
    pdf_text_threshold: int = Field(alias="PDF_TEXT_THRESHOLD")

    # Настройки экспорта
    export_excel_enabled: bool = Field(alias="EXPORT_EXCEL_ENABLED")
    export_crm_enabled: bool = Field(alias="EXPORT_CRM_ENABLED")

    # Настройки Web API
    web_host: str = Field(alias="WEB_HOST", default="0.0.0.0")
    web_port: int = Field(alias="WEB_PORT", default=8000)
    web_auth_token: str = Field(alias="WEB_AUTH_TOKEN", default="")

    # Настройки Telegram Bot
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN", default="")
    telegram_allowed_user_ids: str = Field(alias="TELEGRAM_ALLOWED_USER_IDS", default="")

    @classmethod
    def load(cls) -> "Config":
        """
        Загрузка конфигурации из .env файла

        Returns:
            Экземпляр конфигурации
        """
        return cls()
