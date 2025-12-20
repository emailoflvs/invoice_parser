"""
Telegram Bot адаптер
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from ..core.config import Config
from ..services.orchestrator import Orchestrator
from ..exporters.json_exporter import extract_value_from_field

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram бот для парсинга документов"""

    def __init__(self, config: Config):
        """
        Инициализация бота

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.orchestrator = Orchestrator(config)
        self.allowed_users = self._parse_allowed_users()

    def _parse_allowed_users(self) -> List[int]:
        """
        Парсинг списка разрешенных пользователей

        Returns:
            Список ID разрешенных пользователей
        """
        if not self.config.telegram_allowed_user_ids:
            logger.warning("No allowed users configured for Telegram bot")
            return []

        try:
            user_ids = [
                int(uid.strip())
                for uid in self.config.telegram_allowed_user_ids.split(',')
                if uid.strip()
            ]
            logger.info(f"Allowed users: {user_ids}")
            return user_ids
        except ValueError as e:
            logger.error(f"Failed to parse allowed user IDs: {e}")
            return []

    def _is_authorized(self, user_id: int) -> bool:
        """
        Проверка авторизации пользователя

        Args:
            user_id: ID пользователя

        Returns:
            True если пользователь авторизован
        """
        # Если список пуст, разрешаем всем (небезопасно!)
        if not self.allowed_users:
            logger.warning("No user restrictions - allowing all users")
            return True

        return user_id in self.allowed_users

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text(
                "❌ You do not have access to this bot."
            )
            return

        await update.message.reply_text(
            "👋 Hello! I am a document parsing bot.\n\n"
            "📄 Send me a document (PDF or image), "
            "and I will extract data from it.\n\n"
            "Available commands:\n"
            "/start - Show this message\n"
            "/help - Help\n"
            "/info - Configuration information"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ You do not have access to this bot.")
            return

        await update.message.reply_text(
            "📖 Usage guide:\n\n"
            "1️⃣ Send a document (PDF or image)\n"
            "2️⃣ Wait for processing\n"
            "3️⃣ Receive result in JSON format\n\n"
            "Supported formats:\n"
            "• PDF\n"
            "• JPG/JPEG\n"
            "• PNG\n"
            "• TIFF\n"
            "• BMP\n\n"
            "⚠️ Processing may take up to 30 seconds."
        )

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /info"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ You do not have access to this bot.")
            return

        info_text = (
            f"ℹ️ Configuration information:\n\n"
            f"Mode: {self.config.mode}\n"
            f"Image enhancement: {'✓' if self.config.enable_image_enhancement else '✗'}\n"
            f"PDF mode: {self.config.pdf_processing_mode}\n"
            f"Excel export (local): {'✓' if self.config.export_local_excel_enabled else '✗'}"
        )

        await update.message.reply_text(info_text)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка полученного документа"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ You do not have access to this bot.")
            return

        try:
            # Get document
            if update.message.document:
                file = await update.message.document.get_file()
                file_name = update.message.document.file_name
            elif update.message.photo:
                file = await update.message.photo[-1].get_file()
                file_name = f"photo_{update.message.photo[-1].file_id}.jpg"
            else:
                await update.message.reply_text(
                    "❌ Unsupported file type. "
                    "Please send a document or image."
                )
                return

            # Check file extension
            file_ext = Path(file_name).suffix.lower()
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']

            if file_ext not in allowed_extensions:
                await update.message.reply_text(
                    f"❌ Unsupported file format: {file_ext}\n\n"
                    f"Supported formats: {', '.join(allowed_extensions)}"
                )
                return

            # Processing notification
            status_message = await update.message.reply_text(
                "⏳ Processing document...\n"
                "This may take up to 30 seconds."
            )

            # Сохранение файла
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_ext,
                dir=self.config.temp_dir
            ) as tmp_file:
                await file.download_to_drive(tmp_file.name)
                tmp_path = Path(tmp_file.name)

            logger.info(f"Received document from user {user_id}: {file_name}")

            # Process document (pass original_filename, mode and source)
            # Use "detailed" mode by default for Telegram (same as web form)
            result = await self.orchestrator.process_document(
                tmp_path,
                original_filename=file_name,
                mode="detailed",
                source="telegram"
            )

            # Очистка временного файла
            tmp_path.unlink(missing_ok=True)

            # Отправка результата
            if result["success"]:
                data = result["data"]

                # Извлекаем данные из dict структуры
                # Structure: document_info, parties, table_data, totals
                doc_info = data.get("document_info", {}) if isinstance(data, dict) else {}
                parties = data.get("parties", {}) if isinstance(data, dict) else {}
                table_data = data.get("table_data", {}) if isinstance(data, dict) else {}
                totals = data.get("totals", {}) if isinstance(data, dict) else {}

                # Extract document information (с поддержкой структуры {_label, value})
                invoice_number_raw = doc_info.get("document_number") or doc_info.get("invoice_number")
                invoice_number = extract_value_from_field(invoice_number_raw) or "N/A"

                date_raw = doc_info.get("document_date") or doc_info.get("date")
                date = extract_value_from_field(date_raw) or "N/A"

                # Extract supplier information (use first party from parties if available)
                supplier_name = "N/A"
                if isinstance(parties, dict):
                    # Try to find supplier or first party
                    supplier = parties.get("supplier") or parties.get("buyer") or parties.get("customer")
                    if supplier:
                        if isinstance(supplier, dict):
                            # Extract value from {_label, value} structure
                            name_field = supplier.get("name")
                            if isinstance(name_field, dict) and 'value' in name_field:
                                supplier_name = name_field.get('value', 'N/A')
                            else:
                                supplier_name = name_field or "N/A"

                # Extract total amount
                total_amount = "N/A"
                if isinstance(totals, dict):
                    total_value = totals.get("total") or totals.get("total_amount") or totals.get("total_with_vat")
                    if total_value:
                        if isinstance(total_value, dict) and 'value' in total_value:
                            total_amount = total_value.get('value', 'N/A')
                        else:
                            total_amount = total_value

                # Extract items count
                line_items = table_data.get("line_items", []) if isinstance(table_data, dict) else []
                items_count = len(line_items) if isinstance(line_items, list) else 0

                # Form response
                response_text = (
                    "✅ Document processed successfully!\n\n"
                    f"📋 Document #: {invoice_number}\n"
                    f"📅 Date: {date}\n"
                    f"🏢 Party: {supplier_name}\n"
                    f"💰 Total: {total_amount}\n"
                    f"📦 Items: {items_count}"
                )

                # Send link to edit form via button
                document_id = result.get('document_id')
                keyboard = None

                logger.info(f"Document ID from result: {document_id}")

                if document_id:
                    try:
                        # Build URL for document editing
                        # Use settings from config
                        public_url = self.config.web_public_url

                        if public_url:
                            # Use public URL from config
                            web_url = str(public_url).rstrip('/')
                            logger.info(f"Using public URL from config: {web_url}")
                            edit_url = f"{web_url}/?document_id={document_id}"
                            logger.info(f"Creating edit button with URL: {edit_url}")

                            # Create button with link
                            keyboard = InlineKeyboardMarkup([
                                [InlineKeyboardButton("✏️ Open edit form", url=edit_url)]
                            ])
                        else:
                            # If no public URL configured, cannot create edit link
                            logger.warning("WEB_PUBLIC_URL not configured, cannot create edit link")
                            response_text += f"\n\n✏️ Document ID for editing: {document_id}"
                            keyboard = None
                    except Exception as e:
                        logger.error(f"Failed to create edit button: {e}", exc_info=True)
                        # Add document_id to message as fallback
                        response_text += f"\n\n✏️ Document ID for editing: {document_id}"

                # Update message with button (if available)
                await status_message.edit_text(
                    response_text,
                    reply_markup=keyboard
                )

            else:
                # Get error message
                error_message = result.get('error', 'Unknown error')

                # Parse error code and show only user-friendly message
                user_message = "❌ Failed to process document."

                if "|" in error_message:
                    # Format: ERROR_CODE|User Message
                    parts = error_message.split("|", 1)
                    if len(parts) == 2:
                        user_message = f"⚠️ {parts[1]}"
                elif "ERROR_E" in error_message:
                    # If error code exists, show general message
                    if "E001" in error_message:
                        user_message = "⚠️ Service temporarily unavailable due to high load. Please try again later."
                    elif "E002" in error_message or "E003" in error_message:
                        user_message = "⚙️ Service configuration error. Please contact support."
                    elif "E004" in error_message:
                        user_message = "⏱️ Timeout exceeded. Please try a smaller document."
                    elif "E005" in error_message:
                        user_message = "🌐 Network connection error. Please check your connection and try again."
                    else:
                        user_message = "❌ Failed to process document. Please try again or contact support."
                else:
                    # For other errors show general message
                    user_message = "❌ Failed to process document. Please try again or contact support."

                await status_message.edit_text(user_message)

        except Exception as e:
            logger.error(f"Failed to process document: {e}", exc_info=True)
            error_str = str(e)

            # Parse error message
            user_message = "❌ An error occurred while processing the document. Please try again or contact support."

            if "|" in error_str:
                parts = error_str.split("|", 1)
                if len(parts) == 2:
                    user_message = f"⚠️ {parts[1]}"
            elif "ERROR_E" in error_str:
                if "E001" in error_str:
                    user_message = "⚠️ Service temporarily unavailable due to high load. Please try again later."
                elif "E002" in error_str or "E003" in error_str:
                    user_message = "⚙️ Service configuration error. Please contact support."
                elif "E004" in error_str:
                    user_message = "⏱️ Timeout exceeded. Please try a smaller document."
                elif "E005" in error_str:
                    user_message = "🌐 Network connection error. Please check your connection and try again."

            await update.message.reply_text(user_message)

    def run(self):
        """Start bot"""
        logger.info("Starting Telegram bot")

        # Создание приложения
        application = Application.builder().token(self.config.telegram_bot_token).build()

        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("info", self.info_command))
        application.add_handler(MessageHandler(
            filters.Document.ALL | filters.PHOTO,
            self.handle_document
        ))

        # Запуск
        logger.info("Telegram bot started, polling for updates...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Точка входа для Telegram бота"""
    try:
        config = Config.load()
        bot = TelegramBot(config)
        bot.run()
    except Exception as e:
        logger.error(f"Telegram bot failed: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
