"""
Web API адаптер для REST API
"""
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Depends, Request, Query
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message
from pydantic import BaseModel, Field
from typing import Optional, List

from ..core.config import Config
from ..services.orchestrator import Orchestrator
from ..auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_current_active_user
)
from ..auth.auth import get_user_by_username
from ..database.models import User
from ..database import get_session

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


class RejectRequest(BaseModel):
    """Модель запроса на отмену подтверждения"""
    document_id: int


class RejectResponse(BaseModel):
    """Модель ответа на отмену подтверждения"""
    success: bool
    message: str
    document_id: int
    new_status: str


class HealthResponse(BaseModel):
    """Модель ответа health check"""
    status: str
    version: str
    database: Optional[str] = None


class LoginRequest(BaseModel):
    """Модель запроса на логин"""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Модель ответа на логин"""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class RegisterRequest(BaseModel):
    """Модель запроса на регистрацию"""
    username: str
    email: Optional[str] = None
    password: str


class RegisterResponse(BaseModel):
    """Модель ответа на регистрацию"""
    success: bool
    message: str
    user_id: int
    username: str


class UserResponse(BaseModel):
    """Модель ответа с информацией о пользователе"""
    id: int
    username: str
    email: Optional[str] = None
    is_active: bool
    created_at: str


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

        # Инициализация сервиса экспорта утвержденных данных
        self.export_service = None
        try:
            from ..services.approved_data_export_service import ApprovedDataExportService
            self.export_service = ApprovedDataExportService(config)
            logger.info("ApprovedDataExportService initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize ApprovedDataExportService: {e}")
            self.export_service = None

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
                from sqlalchemy import text
                async for session in get_session():
                    # Простая проверка - попробуем выполнить простой запрос
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

        # Authentication endpoints
        @self.app.post("/api/auth/login", response_model=LoginResponse, tags=["Auth"])
        async def login(login_request: LoginRequest):
            """
            Login with username and password

            Returns:
                JWT access token
            """
            async for session in get_session():
                user = await authenticate_user(session, login_request.username, login_request.password)
                if not user:
                    raise HTTPException(
                        status_code=401,
                        detail="Incorrect username or password"
                    )

                # Create access token
                access_token = create_access_token(data={"sub": user.username})

                # Update last login
                user.last_login = datetime.utcnow()
                await session.commit()

                return LoginResponse(
                    access_token=access_token,
                    token_type="bearer",
                    user_id=user.id,
                    username=user.username
                )

        @self.app.post("/api/auth/register", response_model=RegisterResponse, tags=["Auth"])
        async def register(register_request: RegisterRequest):
            """
            Register a new user

            Returns:
                Registration result
            """
            try:
                async for session in get_session():
                    # Validate password length (bcrypt limit is 72 bytes)
                    if len(register_request.password.encode('utf-8')) > 72:
                        raise HTTPException(
                            status_code=400,
                            detail="Password is too long (maximum 72 bytes)"
                        )

                    # Validate username
                    if not register_request.username or len(register_request.username.strip()) == 0:
                        raise HTTPException(
                            status_code=400,
                            detail="Username cannot be empty"
                        )

                    # Check if user already exists
                    existing_user = await get_user_by_username(session, register_request.username)
                    if existing_user:
                        raise HTTPException(
                            status_code=400,
                            detail="Username already registered"
                        )

                    # Check email if provided
                    if register_request.email:
                        from sqlalchemy import select
                        result = await session.execute(
                            select(User).where(User.email == register_request.email)
                        )
                        if result.scalar_one_or_none():
                            raise HTTPException(
                                status_code=400,
                                detail="Email already registered"
                            )

                    # Create new user
                    try:
                        hashed_password = get_password_hash(register_request.password)
                    except Exception as e:
                        logger.error(f"Failed to hash password: {e}", exc_info=True)
                        raise HTTPException(
                            status_code=500,
                            detail="Failed to process password"
                        )

                    new_user = User(
                        username=register_request.username.strip(),
                        email=register_request.email.strip() if register_request.email else None,
                        hashed_password=hashed_password,
                        is_active=True,
                        is_superuser=False
                    )
                    session.add(new_user)
                    await session.commit()
                    await session.refresh(new_user)

                    logger.info(f"New user registered: {new_user.username} (ID: {new_user.id})")

                    return RegisterResponse(
                        success=True,
                        message="User registered successfully",
                        user_id=new_user.id,
                        username=new_user.username
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Registration error: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Registration failed: {str(e)}"
                )

        @self.app.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
        async def get_current_user_info(
            current_user: User = Depends(get_current_active_user)
        ):
            """
            Get current user information

            Returns:
                Current user data
            """
            return UserResponse(
                id=current_user.id,
                username=current_user.username,
                email=current_user.email,
                is_active=current_user.is_active,
                created_at=current_user.created_at.isoformat() if current_user.created_at else ""
            )

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

            return HealthResponse(
                status="ok" if db_status == "ok" else "degraded",
                version="1.0.0",
                database=db_status
            )

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

        @self.app.get("/api/search/documents", tags=["Search"])
        async def search_documents(
            query: str = Query(..., description="Search query"),
            language: str = Query("simple", description="Language: 'simple' (any), 'russian', 'english'"),
            use_ocr: bool = Query(True, description="Search in OCR text"),
            use_fields: bool = Query(True, description="Search in field values"),
            current_user: User = Depends(get_current_active_user)
        ):
            """
            Full-text search in documents.

            Language options:
            - 'simple': Works with any language (recommended for multilingual documents)
            - 'russian': Optimized for Russian text
            - 'english': Optimized for English text
            """

            try:
                from ..database import get_session

                db_service = self.orchestrator.db_service
                if not db_service:
                    raise HTTPException(status_code=503, detail="Database service not available")

                async for session in get_session():
                    documents = await db_service.search_documents_by_text(
                        session=session,
                        search_text=query,
                        language=language,
                        use_ocr=use_ocr,
                        use_field_values=use_fields
                    )
                    return {
                        "count": len(documents),
                        "documents": [
                            {
                                "id": doc.id,
                                "status": doc.status,
                                "language": doc.language,
                                "country": doc.country,
                                "created_at": doc.created_at.strftime("%Y-%m-%d %H:%M") if doc.created_at else None
                            }
                            for doc in documents
                        ]
                    }
            except Exception as e:
                logger.error(f"Search failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/parse", response_model=ParseResponse)
        async def parse_document(
            file: UploadFile = File(...),
            mode: str = "detailed",
            current_user: User = Depends(get_current_active_user)
        ):
            """
            Parse uploaded document

            Args:
                file: Uploaded document (PDF or image)
                mode: Режим обработки - "fast" (быстрый) или "detailed" (детальный)
                current_user: Current authenticated user

            Returns:
                Parsing result
            """

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
                result = await self.orchestrator.process_document(tmp_path, original_filename=file.filename, mode=mode)

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
            current_user: User = Depends(get_current_active_user)
        ):
            """
            Save edited document data to JSON file

            Args:
                save_request: Request with original filename and edited data
                current_user: Current authenticated user

            Returns:
                Save result with new filename
            """

            try:
                import json
                from ..utils.datetime_utils import now

                # Создаем директорию output если её нет
                output_dir = Path(self.config.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # Генерируем имя файла
                # Формат времени: ddmmhhmm (день, месяц, час, минута)
                timestamp = now().strftime("%d%m%H%M")
                base_name = Path(save_request.original_filename).stem
                new_filename = f"{base_name}_{timestamp}_saved.json"
                output_path = output_dir / new_filename

                # Сохраняем данные в файл
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(save_request.data, f, indent=2, ensure_ascii=False)

                logger.info(f"Saved edited data to: {output_path}")

                # Сохранение APPROVED данных в базу данных
                document_id = save_request.data.get('document_id')  # ID документа из RAW сохранения
                if document_id:
                    try:
                        await self._save_approved_to_database(document_id, save_request.data, current_user.id)
                        logger.info(f"✅ APPROVED data saved to database (document_id: {document_id})")
                    except Exception as e:
                        logger.error(f"Failed to save APPROVED data to database: {e}", exc_info=True)
                        # Не падаем, файл уже сохранен
                else:
                    logger.warning("No document_id in save request, skipping database save")

                # Экспорт APPROVED данных во все включенные форматы (Excel, Google Sheets)
                if self.export_service:
                    try:
                        export_results = await self.export_service.export_approved_data(
                            approved_data=save_request.data,
                            original_filename=save_request.original_filename
                        )

                        # Логируем результаты
                        if export_results.get('excel', {}).get('success'):
                            logger.info(f"✅ APPROVED data exported to Excel: {export_results['excel']['path']}")
                        elif export_results.get('excel', {}).get('error'):
                            logger.warning(f"Excel export failed: {export_results['excel']['error']}")

                        if export_results.get('sheets', {}).get('success'):
                            logger.info(f"✅ APPROVED data exported to Google Sheets")
                        elif export_results.get('sheets', {}).get('error'):
                            logger.warning(f"Google Sheets export failed: {export_results['sheets']['error']}")
                    except Exception as e:
                        logger.error(f"Failed to export APPROVED data: {e}", exc_info=True)
                        # Не падаем, данные уже сохранены в файл и БД

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

        @self.app.post("/reject", response_model=RejectResponse)
        async def reject_approved_document(
            reject_request: RejectRequest,
            current_user: User = Depends(get_current_active_user)
        ):
            """
            Отменить подтверждение документа (вернуть статус в 'parsed')

            Args:
                reject_request: Request with document_id
                current_user: Current authenticated user

            Returns:
                Reject result with new status
            """
            try:
                from ..database import get_session
                from ..database.service import DatabaseService

                # Создаем DatabaseService если еще нет
                db_service = DatabaseService(
                    database_url=self.config.database_url,
                    echo=self.config.db_echo,
                    pool_size=self.config.db_pool_size,
                    max_overflow=self.config.db_max_overflow
                )

                async for session in get_session():
                    document = await db_service.reject_approved_document(
                        session=session,
                        document_id=reject_request.document_id,
                        user_id=current_user.id
                    )
                    break

                logger.info(f"✅ Document approval rejected (document_id: {reject_request.document_id}, status: {document.status})")

                return RejectResponse(
                    success=True,
                    message="Подтверждение документа отменено",
                    document_id=reject_request.document_id,
                    new_status=document.status
                )

            except ValueError as e:
                logger.error(f"Document not found: {e}")
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error_code": "DOCUMENT_NOT_FOUND",
                        "message": f"Документ не найден: {str(e)}"
                    }
                )
            except Exception as e:
                logger.error(f"Failed to reject document: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error_code": "REJECT_ERROR",
                        "message": f"Не удалось отменить подтверждение: {str(e)}"
                    }
                )

        @self.app.get("/login.html")
        async def login_page():
            """Страница входа"""
            static_dir = Path(__file__).parent.parent.parent.parent / "static"
            login_file = static_dir / "login.html"

            if not login_file.exists():
                raise HTTPException(status_code=404, detail="Login page not found")

            with open(login_file, 'r', encoding='utf-8') as f:
                content = f.read()

            return Response(
                content=content,
                media_type="text/html",
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
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

    async def _save_approved_to_database(self, document_id: int, approved_data: dict, user_id: int) -> None:
        """
        Сохранение APPROVED данных в базу данных

        Args:
            document_id: ID документа в БД
            approved_data: Утвержденные данные
            user_id: ID пользователя, который утвердил данные
        """
        try:
            from ..database import get_session
            from ..database.service import DatabaseService

            # Создаем DatabaseService если еще нет
            db_service = DatabaseService(
                database_url=self.config.database_url,
                echo=self.config.db_echo,
                pool_size=self.config.db_pool_size,
                max_overflow=self.config.db_max_overflow
            )

            async for session in get_session():
                await db_service.save_approved_document(
                    session=session,
                    document_id=document_id,
                    approved_json=approved_data,
                    user_id=user_id
                )
                break
        except Exception as e:
            logger.error(f"Database approved save error: {e}", exc_info=True)
            raise

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
