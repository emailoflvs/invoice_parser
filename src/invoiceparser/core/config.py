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
    export_local_excel_enabled: bool = Field(alias="EXPORT_LOCAL_EXCEL_ENABLED")
    export_crm_enabled: bool = Field(alias="EXPORT_CRM_ENABLED")

    # Настройки Excel экспорта
    excel_sheet_header_name: str = Field(
        alias="EXCEL_SHEET_HEADER_NAME",
        default="Реквизиты"
    )  # Название листа для реквизитов документа
    excel_sheet_items_name: str = Field(
        alias="EXCEL_SHEET_ITEMS_NAME",
        default="Позиции"
    )  # Название листа для позиций документа
    excel_header_field_column: str = Field(
        alias="EXCEL_HEADER_FIELD_COLUMN",
        default="Поле"
    )  # Название колонки для полей в листе реквизитов
    excel_header_value_column: str = Field(
        alias="EXCEL_HEADER_VALUE_COLUMN",
        default="Значение"
    )  # Название колонки для значений в листе реквизитов
    excel_default_sheet_name: str = Field(
        alias="EXCEL_DEFAULT_SHEET_NAME",
        default="Sheet"
    )  # Название стандартного листа openpyxl для удаления

    # Настройки Web API
    web_host: str = Field(alias="WEB_HOST", default="0.0.0.0")
    web_port: int = Field(alias="WEB_PORT", default=8000)
    web_auth_token: str = Field(alias="WEB_AUTH_TOKEN", default="")
    max_file_size_mb: int = Field(alias="MAX_FILE_SIZE_MB", default=50)  # Максимальный размер загружаемого файла в МБ
    reload_dirs: str = Field(alias="RELOAD_DIRS", default="")  # Директории для auto-reload (через запятую, пусто = автоматически)

    # Настройки Telegram Bot
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN", default="")
    telegram_allowed_user_ids: str = Field(alias="TELEGRAM_ALLOWED_USER_IDS", default="")

    # Database settings
    database_url: str = Field(
        alias="DATABASE_URL",
        default="postgresql+asyncpg://invoiceparser:invoiceparser_password@db:5432/invoiceparser"
    )
    db_echo: bool = Field(alias="DB_ECHO", default=False)  # SQLAlchemy query logging
    db_pool_size: int = Field(alias="DB_POOL_SIZE", default=50)  # Increased for high load (was 5)
    db_max_overflow: int = Field(alias="DB_MAX_OVERFLOW", default=20)  # Increased for high load (was 10)
    db_auto_migrate: bool = Field(alias="DB_AUTO_MIGRATE", default=True)  # Auto-run migrations on startup

    # Database maintenance settings
    archive_partitions_older_than_years: int = Field(
        alias="ARCHIVE_PARTITIONS_OLDER_THAN_YEARS",
        default=2
    )  # Архивировать партиции старше N лет
    duplicate_check_window_seconds: int = Field(
        alias="DUPLICATE_CHECK_WINDOW_SECONDS",
        default=60
    )  # Окно проверки дублей при парсинге (в секундах)

    # Database search settings
    fts_languages: str = Field(
        alias="FTS_LANGUAGES",
        default="simple,russian,english"
    )  # Языки для FTS индексов (через запятую)
    fts_partial_index_languages: str = Field(
        alias="FTS_PARTIAL_INDEX_LANGUAGES",
        default="ru,uk"
    )  # Языки для partial FTS индексов (через запятую)

    # Company normalization settings
    normalize_tax_id: bool = Field(
        alias="NORMALIZE_TAX_ID",
        default=True
    )  # Включить нормализацию tax_id
    tax_id_fallback_to_name: bool = Field(
        alias="TAX_ID_FALLBACK_TO_NAME",
        default=True
    )  # Искать по имени, если tax_id не найден

    # Transaction settings
    db_transaction_timeout: int = Field(
        alias="DB_TRANSACTION_TIMEOUT",
        default=30
    )  # Timeout для транзакций (в секундах)

    # Retry settings for external APIs
    api_retry_attempts: int = Field(
        alias="API_RETRY_ATTEMPTS",
        default=3
    )  # Количество попыток retry для AI API
    api_retry_min_wait: int = Field(
        alias="API_RETRY_MIN_WAIT",
        default=2
    )  # Минимальная задержка между попытками (секунды)
    api_retry_max_wait: int = Field(
        alias="API_RETRY_MAX_WAIT",
        default=10
    )  # Максимальная задержка между попытками (секунды)

    # Google Sheets (Online Excel) settings
    export_online_excel_enabled: bool = Field(
        alias="EXPORT_ONLINE_EXCEL_ENABLED",
        default=False
    )  # Включить экспорт в Google Sheets (онлайн Excel)
    sheets_spreadsheet_id: str = Field(
        alias="SHEETS_SPREADSHEET_ID",
        default=""
    )  # ID Google Spreadsheet
    sheets_credentials_path: str = Field(
        alias="SHEETS_CREDENTIALS_PATH",
        default=""
    )  # Путь к JSON файлу с credentials для Google Sheets API
    sheets_header_sheet: str = Field(
        alias="SHEETS_HEADER_SHEET",
        default="Реквизиты"
    )  # Название листа для сохранения реквизитов (header) в Google Sheets
    sheets_items_sheet: str = Field(
        alias="SHEETS_ITEMS_SHEET",
        default="Позиции"
    )  # Название листа для сохранения позиций (items) в Google Sheets

    @classmethod
    def load(cls) -> "Config":
        """
        Загрузка конфигурации из .env файла

        Returns:
            Экземпляр конфигурации
        """
        return cls()
