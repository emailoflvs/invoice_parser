"""
Web API адаптер для REST API
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.config import Config
from ..services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


class ParseResponse(BaseModel):
    """Модель ответа на запрос парсинга"""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    processed_at: str


class HealthResponse(BaseModel):
    """Модель ответа health check"""
    status: str
    version: str


class WebAPI:
    """Web API для парсинга документов"""

    def __init__(self, config: Config):
        """
        Инициализация Web API

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.orchestrator = Orchestrator(config)
        self.app = FastAPI(
            title="InvoiceParser API",
            description="AI-powered document parsing API",
            version="1.0.0"
        )

        self._setup_routes()

    def _setup_routes(self):
        """Настройка маршрутов"""

        @self.app.get("/health", response_model=HealthResponse)
        async def health():
            """Health check endpoint"""
            return {
                "status": "ok",
                "version": "1.0.0"
            }

        @self.app.post("/parse", response_model=ParseResponse)
        async def parse_document(
            file: UploadFile = File(...),
            token: Optional[str] = Header(None, alias="Authorization")
        ):
            """
            Parse uploaded document

            Args:
                file: Uploaded document (PDF or image)
                token: Authorization token

            Returns:
                Parsing result
            """
            # Проверка авторизации
            if not self._verify_token(token):
                raise HTTPException(status_code=401, detail="Unauthorized")

            # Проверка типа файла
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']
            file_ext = Path(file.filename).suffix.lower()

            if file_ext not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file format: {file_ext}"
                )

            # Сохранение файла во временную директорию
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=file_ext,
                    dir=self.config.temp_dir
                ) as tmp_file:
                    content = await file.read()
                    tmp_file.write(content)
                    tmp_path = Path(tmp_file.name)

                logger.info(f"Received file: {file.filename}, saved to: {tmp_path}")

                # Обработка документа
                result = self.orchestrator.process_document(tmp_path)

                # Очистка временного файла
                tmp_path.unlink(missing_ok=True)

                # Формирование ответа
                if result["success"]:
                    return ParseResponse(
                        success=True,
                        data=result["data"].model_dump() if hasattr(result["data"], "model_dump") else result["data"],
                        processed_at=result["processed_at"]
                    )
                else:
                    return ParseResponse(
                        success=False,
                        error=result.get("error", "Unknown error"),
                        processed_at=result["processed_at"]
                    )

            except Exception as e:
                logger.error(f"Failed to process upload: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/")
        async def root():
            """Root endpoint"""
            return {
                "name": "InvoiceParser API",
                "version": "1.0.0",
                "endpoints": {
                    "health": "/health",
                    "parse": "/parse (POST)"
                }
            }

    def _verify_token(self, token: Optional[str]) -> bool:
        """
        Проверка токена авторизации

        Args:
            token: Токен из заголовка Authorization

        Returns:
            True если токен валидный
        """
        if not token:
            return False

        # Удаление префикса Bearer
        if token.startswith("Bearer "):
            token = token[7:]

        return token == self.config.web_auth_token

    def run(self, host: Optional[str] = None, port: Optional[int] = None):
        """
        Запуск веб-сервера

        Args:
            host: Хост (по умолчанию из конфига)
            port: Порт (по умолчанию из конфига)
        """
        import uvicorn

        host = host or self.config.web_host
        port = port or self.config.web_port

        logger.info(f"Starting web server on {host}:{port}")

        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level=self.config.log_level.lower()
        )


def create_app(config: Optional[Config] = None) -> FastAPI:
    """
    Создание FastAPI приложения

    Args:
        config: Конфигурация (если None, загружается автоматически)

    Returns:
        FastAPI приложение
    """
    if config is None:
        config = Config.load()

    api = WebAPI(config)
    return api.app
