"""
Telegram Bot адаптер
"""
import logging
import tempfile
from pathlib import Path
from typing import Optional, List
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from ..core.config import Config
from ..services.orchestrator import Orchestrator

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
                "❌ У вас нет доступа к этому боту."
            )
            return

        await update.message.reply_text(
            "👋 Привет! Я бот для парсинга документов.\n\n"
            "📄 Отправьте мне документ (PDF или изображение), "
            "и я извлеку из него данные.\n\n"
            "Доступные команды:\n"
            "/start - Показать это сообщение\n"
            "/help - Справка\n"
            "/info - Информация о конфигурации"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /help"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return

        await update.message.reply_text(
            "📖 Справка по использованию:\n\n"
            "1️⃣ Отправьте документ (PDF или изображение)\n"
            "2️⃣ Дождитесь обработки\n"
            "3️⃣ Получите результат в формате JSON\n\n"
            "Поддерживаемые форматы:\n"
            "• PDF\n"
            "• JPG/JPEG\n"
            "• PNG\n"
            "• TIFF\n"
            "• BMP\n\n"
            "⚠️ Обработка может занять до 30 секунд."
        )

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /info"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return

        info_text = (
            f"ℹ️ Информация о конфигурации:\n\n"
            f"Режим: {self.config.mode}\n"
            f"Улучшение изображений: {'✓' if self.config.enable_image_enhancement else '✗'}\n"
            f"Режим PDF: {self.config.pdf_processing_mode}\n"
            f"Экспорт в Excel: {'✓' if self.config.export_excel_enabled else '✗'}"
        )

        await update.message.reply_text(info_text)

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка полученного документа"""
        user_id = update.effective_user.id

        if not self._is_authorized(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return

        try:
            # Получение документа
            if update.message.document:
                file = await update.message.document.get_file()
                file_name = update.message.document.file_name
            elif update.message.photo:
                file = await update.message.photo[-1].get_file()
                file_name = f"photo_{update.message.photo[-1].file_id}.jpg"
            else:
                await update.message.reply_text(
                    "❌ Неподдерживаемый тип файла. "
                    "Отправьте документ или изображение."
                )
                return

            # Проверка расширения
            file_ext = Path(file_name).suffix.lower()
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']

            if file_ext not in allowed_extensions:
                await update.message.reply_text(
                    f"❌ Неподдерживаемый формат файла: {file_ext}\n\n"
                    f"Поддерживаемые форматы: {', '.join(allowed_extensions)}"
                )
                return

            # Уведомление о начале обработки
            status_message = await update.message.reply_text(
                "⏳ Обработка документа...\n"
                "Это может занять до 30 секунд."
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

            # Обработка документа
            result = self.orchestrator.process_document(tmp_path)

            # Очистка временного файла
            tmp_path.unlink(missing_ok=True)

            # Отправка результата
            if result["success"]:
                data = result["data"]

                # Формирование ответа
                response_text = (
                    "✅ Документ обработан успешно!\n\n"
                    f"📋 Номер счета: {data.header.invoice_number}\n"
                    f"📅 Дата: {data.header.date}\n"
                    f"🏢 Поставщик: {data.header.supplier_name}\n"
                    f"💰 Сумма: {data.header.total_amount}\n"
                    f"📦 Позиций: {len(data.items)}"
                )

                await status_message.edit_text(response_text)

                # Отправка JSON файла
                import json
                json_data = data.model_dump() if hasattr(data, "model_dump") else data
                json_str = json.dumps(json_data, indent=2, ensure_ascii=False)

                await update.message.reply_document(
                    document=json_str.encode('utf-8'),
                    filename=f"{data.header.invoice_number or 'result'}.json",
                    caption="📄 Полные данные в JSON"
                )

            else:
                # Получаем сообщение об ошибке
                error_message = result.get('error', 'Неизвестная ошибка')

                # Парсим код ошибки и показываем только понятное сообщение
                user_message = "❌ Не удалось обработать документ."

                if "|" in error_message:
                    # Формат: ERROR_CODE|User Message
                    parts = error_message.split("|", 1)
                    if len(parts) == 2:
                        user_message = f"⚠️ {parts[1]}"
                elif "ERROR_E" in error_message:
                    # Если есть код ошибки, показываем общее сообщение
                    if "E001" in error_message:
                        user_message = "⚠️ Сервис временно недоступен из-за высокой нагрузки. Попробуйте позже."
                    elif "E002" in error_message or "E003" in error_message:
                        user_message = "⚙️ Ошибка конфигурации сервиса. Обратитесь в поддержку."
                    elif "E004" in error_message:
                        user_message = "⏱️ Превышено время ожидания. Попробуйте документ меньшего размера."
                    elif "E005" in error_message:
                        user_message = "🌐 Ошибка сетевого подключения. Проверьте соединение и попробуйте снова."
                    else:
                        user_message = "❌ Не удалось обработать документ. Попробуйте снова или обратитесь в поддержку."
                else:
                    # Для других ошибок показываем общее сообщение
                    user_message = "❌ Не удалось обработать документ. Попробуйте снова или обратитесь в поддержку."

                await status_message.edit_text(user_message)

        except Exception as e:
            logger.error(f"Failed to process document: {e}", exc_info=True)
            error_str = str(e)

            # Парсим сообщение об ошибке
            user_message = "❌ Произошла ошибка при обработке документа. Попробуйте снова или обратитесь в поддержку."

            if "|" in error_str:
                parts = error_str.split("|", 1)
                if len(parts) == 2:
                    user_message = f"⚠️ {parts[1]}"
            elif "ERROR_E" in error_str:
                if "E001" in error_str:
                    user_message = "⚠️ Сервис временно недоступен из-за высокой нагрузки. Попробуйте позже."
                elif "E002" in error_str or "E003" in error_str:
                    user_message = "⚙️ Ошибка конфигурации сервиса. Обратитесь в поддержку."
                elif "E004" in error_str:
                    user_message = "⏱️ Превышено время ожидания. Попробуйте документ меньшего размера."
                elif "E005" in error_str:
                    user_message = "🌐 Ошибка сетевого подключения. Проверьте соединение и попробуйте снова."

            await update.message.reply_text(user_message)

    def run(self):
        """Запуск бота"""
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
