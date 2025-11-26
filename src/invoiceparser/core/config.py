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
    mode: Literal["NORMAL", "TEST"] = "NORMAL"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    
    # Директории
    invoices_dir: Path = Path("/app/invoices")
    output_dir: Path = Path("/app/output")
    logs_dir: Path = Path("/app/logs")
    temp_dir: Path = Path("/app/output/temp")
    examples_dir: Path = Path("/app/examples")
    
    # Gemini API
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash-exp", alias="GEMINI_MODEL")
    gemini_timeout: int = Field(default=35, alias="GEMINI_TIMEOUT")
    vision_seed: str = "random"
    prompts_dir: Path = Path("/app/prompts")
    prompt_header_path: Path = Path("/app/prompts/header.txt")
    prompt_items_path: Path = Path("/app/prompts/items.txt")
    
    # Настройки изображений
    enable_image_enhancement: bool = True
    image_upscale_factor: float = 2.0
    image_brightness_factor: float = 1.1
    image_contrast_factor: float = 1.2
    image_sharpness_factor: float = 1.5
    image_color_factor: float = 1.0
    image_unsharp_radius: float = 2.0
    image_unsharp_percent: int = 150
    image_unsharp_threshold: int = 3
    image_denoise_strength: float = 0.3
    image_binarize: bool = False
    image_binarize_threshold: int = 128
    image_dilate: bool = False
    image_dilate_kernel: int = 2
    image_dpi: int = 300
    image_format: Literal["PNG", "JPEG"] = "PNG"
    image_quality: int = 95
    
    # Настройки PDF
    pdf_processing_mode: Literal["DIRECT", "IMAGE_BASED", "HYBRID"] = "HYBRID"
    pdf_image_dpi: int = 300
    pdf_max_pages: int = 50
    pdf_text_threshold: int = 100
    
    # Настройки экспорта
    export_excel_enabled: bool = True
    export_crm_enabled: bool = False
    
    @classmethod
    def load(cls) -> "Config":
        """
        Загрузка конфигурации из .env файла
        
        Returns:
            Экземпляр конфигурации
        """
        return cls()
