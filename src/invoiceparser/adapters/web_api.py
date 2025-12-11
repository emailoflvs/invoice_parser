"""
Web API адаптер для REST API
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from pydantic import BaseModel

from ..core.config import Config
from ..services.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Константы
BEARER_PREFIX = "Bearer "


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
    database: Optional[str] = None


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

        # Подключение статических файлов с отключением кэша
        static_dir = Path(__file__).parent.parent.parent.parent / "static"
        logger.info(f"Static directory: {static_dir}, exists: {static_dir.exists()}")

        # Сохраняем путь к статическим файлам
        self.static_dir = static_dir

        if static_dir.exists():
            # ВАЖНО: Регистрируем кастомный роут ПЕРЕД mount, чтобы он имел приоритет
            # FastAPI обрабатывает роуты перед mount, поэтому этот роут будет вызываться первым
            @self.app.get("/static/{file_path:path}")
            async def serve_static_file(file_path: str):
                """Отдача статических файлов с no-cache заголовками, читая напрямую из файловой системы"""
                file_full_path = static_dir / file_path

                # Проверяем безопасность пути (предотвращаем path traversal)
                try:
                    file_full_path.resolve().relative_to(static_dir.resolve())
                except ValueError:
                    raise HTTPException(status_code=403, detail="Access denied")

                if file_full_path.exists() and file_full_path.is_file():
                    # Читаем файл напрямую из файловой системы
                    with open(file_full_path, 'rb') as f:
                        content = f.read()

                    logger.info(f"Serving static file: {file_path}, size: {len(content)} bytes")

                    # Определяем media type
                    if file_path.endswith('.js'):
                        media_type = "application/javascript"
                    elif file_path.endswith('.css'):
                        media_type = "text/css"
                    elif file_path.endswith('.html'):
                        media_type = "text/html"
                    else:
                        media_type = "application/octet-stream"

                    return Response(
                        content=content,
                        media_type=media_type,
                        headers={
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0"
                        }
                    )
                else:
                    logger.warning(f"Static file not found: {file_full_path}")
                    raise HTTPException(status_code=404, detail="File not found")

            logger.info(f"Static files route registered from: {static_dir} (no-cache enabled, direct file reading)")

        # Подключение директории с invoices для тестирования
        invoices_dir = Path(__file__).parent.parent.parent.parent / "invoices"
        if invoices_dir.exists():
            self.app.mount("/invoices", StaticFiles(directory=str(invoices_dir)), name="invoices")
            logger.info(f"Invoices directory mounted from: {invoices_dir}")

        self._setup_routes()
        self._setup_database()

        # Добавляем тестовый роут для проверки
        @self.app.get("/test-static-path")
        async def test_static_path():
            """Тестовый роут для проверки пути к статическим файлам"""
            return {
                "static_dir": str(self.static_dir),
                "exists": self.static_dir.exists(),
                "script_js_exists": (self.static_dir / "script.js").exists(),
                "script_js_size": (self.static_dir / "script.js").stat().st_size if (self.static_dir / "script.js").exists() else 0
            }

    def _setup_database(self):
        """Настройка базы данных"""
        from ..database import init_db, close_db

        @self.app.on_event("startup")
        async def startup_event():
            """Инициализация БД при запуске приложения"""
            try:
                logger.info("Initializing database...")
                init_db(
                    database_url=self.config.database_url,
                    echo=self.config.db_echo,
                    pool_size=self.config.db_pool_size,
                    max_overflow=self.config.db_max_overflow
                )

                # Проверяем подключение к БД
                from ..database import get_session
                async for session in get_session():
                    # Простая проверка - попробуем выполнить простой запрос
                    from sqlalchemy import text
                    await session.execute(text("SELECT 1"))
                    logger.info("✅ Database connection established")
                    break

                # Автоматический запуск миграций (если включен)
                if self.config.db_auto_migrate:
                    try:
                        import subprocess
                        import sys
                        logger.info("Running database migrations...")
                        result = subprocess.run(
                            [sys.executable, "-m", "alembic", "upgrade", "head"],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            logger.info("✅ Database migrations completed")
                        else:
                            logger.warning(f"⚠️ Migration output: {result.stdout}")
                            if result.stderr:
                                logger.warning(f"Migration errors: {result.stderr}")
                    except subprocess.TimeoutExpired:
                        logger.warning("⚠️ Migration timeout - migrations may still be running")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not run migrations automatically: {e}")
                        logger.info("You can run migrations manually: alembic upgrade head")
                else:
                    logger.info("Auto-migration disabled (DB_AUTO_MIGRATE=false)")

            except Exception as e:
                logger.error(f"❌ Failed to initialize database: {e}")
                # В dev режиме не падаем, в production можно добавить exit
                if not self.config.dev_mode:
                    raise

        @self.app.on_event("shutdown")
        async def shutdown_event():
            """Закрытие подключения к БД при остановке приложения"""
            try:
                logger.info("Closing database connections...")
                await close_db()
                logger.info("✅ Database connections closed")
            except Exception as e:
                logger.error(f"Error closing database: {e}")

    def _setup_routes(self):
        """Настройка маршрутов"""

        @self.app.get("/health", response_model=HealthResponse)
        async def health():
            """Health check endpoint"""
            db_status = "unknown"
            try:
                from ..database import get_session
                from sqlalchemy import text
                async for session in get_session():
                    await session.execute(text("SELECT 1"))
                    db_status = "ok"
                    break
            except Exception as e:
                logger.warning(f"Database health check failed: {e}")
                db_status = "error"

            return {
                "status": "ok" if db_status == "ok" else "degraded",
                "version": "1.0.0",
                "database": db_status
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
            mode: str = "detailed",
            token: Optional[str] = Header(None, alias="Authorization")
        ):
            """
            Parse uploaded document

            Args:
                file: Uploaded document (PDF or image)
                mode: Режим обработки - "fast" (быстрый) или "detailed" (детальный)
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

                # Проверка размера файла
                max_size = self.config.max_file_size_mb * 1024 * 1024
                if len(content) > max_size:
                    size_mb = len(content) / 1024 / 1024
                    logger.warning(f"Rejected file: too large ({size_mb:.1f}MB)")
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "error_code": "FILE_TOO_LARGE",
                            "message": f"Файл слишком большой ({size_mb:.1f}МБ). Максимальный размер: {self.config.max_file_size_mb}МБ."
                        }
                    )

                with tempfile.NamedTemporaryFile(
                    delete=False,
                    suffix=file_ext,
                    dir=self.config.temp_dir
                ) as tmp_file:
                    tmp_file.write(content)
                    tmp_path = Path(tmp_file.name)

                logger.info(f"Received file: {file.filename}, saved to: {tmp_path}, mode: {mode}")

                # Валидация режима
                if mode not in ["fast", "detailed"]:
                    mode = "detailed"  # По умолчанию детальный режим

                # Обработка документа (передаем оригинальное имя файла и режим)
                result = self.orchestrator.process_document(tmp_path, original_filename=file.filename, mode=mode)

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
        if token.startswith(BEARER_PREFIX):
            token = token[len(BEARER_PREFIX):]

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

        # В dev-режиме включаем auto-reload для автоматической перезагрузки при изменениях
        reload = self.config.dev_mode

        logger.info(f"Starting web server on {host}:{port} (dev_mode={reload})")
        if reload:
            logger.info("⚡ Auto-reload enabled - code changes will be applied automatically")

        # Для reload нужно передавать строку импорта, а не объект app
        if reload:
            # Определяем директории для reload
            if self.config.reload_dirs:
                # Если указано в config - используем указанные
                reload_dirs = [d.strip() for d in self.config.reload_dirs.split(",") if d.strip()]
            else:
                # Автоматически определяем путь к src
                # Путь относительно текущего файла: web_api.py -> src/invoiceparser/adapters/
                src_path = Path(__file__).parent.parent.parent.parent / "src"
                reload_dirs = [str(src_path.resolve())]

            uvicorn.run(
                "invoiceparser.adapters.web_api:create_app",
                host=host,
                port=port,
                log_level=self.config.log_level.lower(),
                reload=True,
                reload_dirs=reload_dirs,
                factory=True  # create_app - это фабрика
            )
        else:
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
