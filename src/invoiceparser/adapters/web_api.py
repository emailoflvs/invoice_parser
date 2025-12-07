"""
Web API адаптер для REST API
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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


class SaveRequest(BaseModel):
    """Модель запроса на сохранение данных"""
    original_filename: str
    data: dict


class SaveResponse(BaseModel):
    """Модель ответа на сохранение"""
    success: bool
    filename: str
    message: Optional[str] = None
    error: Optional[str] = None


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
            title="Анализ документов API",
            description="API для обработки и анализа счетов и накладных",
            version="1.0.0"
        )

        # Настройка CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # В продакшене указать конкретные домены
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Подключение статических файлов
        static_dir = Path(__file__).parent.parent.parent.parent / "static"
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            logger.info(f"Static files mounted from: {static_dir}")

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

        @self.app.get("/api/validate-frontend")
        async def validate_frontend():
            """
            Проверка совместимости API с фронтендом

            Проверяет структуру данных, которую ожидает получить фронтенд
            """
            from invoiceparser.utils.frontend_validator import validate_api_structure

            results = validate_api_structure()

            return {
                "success": results["success"],
                "checks": results["checks"],
                "errors": results["errors"],
                "warnings": results["warnings"],
                "summary": results["summary"]
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
                logger.warning(f"Rejected file with unsupported extension: {file_ext}")
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_code": "INVALID_FORMAT",
                        "message": f"Неподдерживаемый формат файла. Загрузите PDF, JPG, PNG, TIFF или BMP."
                    }
                )

            # Сохранение файла во временную директорию
            try:
                # Читаем содержимое файла
                content = await file.read()

                # Проверка размера файла (50MB)
                max_size = 50 * 1024 * 1024
                if len(content) > max_size:
                    size_mb = len(content) / 1024 / 1024
                    logger.warning(f"Rejected file: too large ({size_mb:.1f}MB)")
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "error_code": "FILE_TOO_LARGE",
                            "message": f"Файл слишком большой ({size_mb:.1f}МБ). Максимальный размер: 50МБ."
                        }
                    )

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=file_ext,
                    dir=self.config.temp_dir
                ) as tmp_file:
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
                error_message = str(e)
                logger.error(f"Failed to process upload: {e}", exc_info=True)

                # Парсим код ошибки и сообщение (формат: ERROR_CODE|User Message)
                error_code = "E099"
                user_message = "Unable to process document. Please try again or contact support."

                if "|" in error_message:
                    parts = error_message.split("|", 1)
                    if len(parts) == 2:
                        error_code = parts[0].replace("ERROR_", "")
                        user_message = parts[1]
                        logger.info(f"Sending user message: {user_message} (Internal code: {error_code})")
                else:
                    # Для других исключений
                    logger.error(f"Unformatted error: {error_message}")
                    user_message = str(e)

                # Определяем HTTP статус код на основе кода ошибки
                status_code = 500
                if error_code == "E001":  # Quota
                    status_code = 503  # Service Unavailable
                elif error_code in ["E002", "E003"]:  # Config errors
                    status_code = 500  # Internal Server Error
                elif error_code == "E004":  # Timeout
                    status_code = 504  # Gateway Timeout
                elif error_code == "E005":  # Network
                    status_code = 503  # Service Unavailable

                raise HTTPException(
                    status_code=status_code,
                    detail={
                        "error_code": error_code,
                        "message": user_message
                    }
                )

        @self.app.post("/save", response_model=SaveResponse)
        async def save_edited_data(
            save_request: SaveRequest,
            token: Optional[str] = Header(None, alias="Authorization")
        ):
            """
            Save edited document data to JSON file

            Args:
                save_request: Request with original filename and edited data
                token: Authorization token

            Returns:
                Save result with new filename
            """
            # Проверка авторизации
            if not self._verify_token(token):
                raise HTTPException(status_code=401, detail="Unauthorized")

            try:
                import json
                from datetime import datetime

                # Создаем директорию output если её нет
                output_dir = Path(self.config.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # Генерируем имя файла
                timestamp = datetime.now().strftime("%d%m%H%M")
                base_name = Path(save_request.original_filename).stem
                new_filename = f"{base_name}_saved_{timestamp}.json"
                output_path = output_dir / new_filename

                # Сохраняем данные
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(save_request.data, f, indent=2, ensure_ascii=False)

                logger.info(f"Saved edited data to: {output_path}")

                return SaveResponse(
                    success=True,
                    filename=new_filename,
                    message=f"Данные успешно сохранены в файл {new_filename}"
                )

            except Exception as e:
                logger.error(f"Failed to save data: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_code": "SAVE_ERROR",
                        "message": f"Не удалось сохранить данные: {str(e)}"
                    }
                )

        @self.app.get("/")
        async def root():
            """Root endpoint - returns web interface"""
            static_dir = Path(__file__).parent.parent.parent.parent / "static"
            index_file = static_dir / "index.html"

            if index_file.exists():
                return FileResponse(index_file)
            else:
                return {
                    "name": "InvoiceParser API",
                    "version": "1.0.0",
                    "endpoints": {
                        "health": "/health",
                        "parse": "/parse (POST)",
                        "save": "/save (POST)"
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
