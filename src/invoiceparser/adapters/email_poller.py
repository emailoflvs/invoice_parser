"""
Email Poller адаптер для получения документов из почты
"""
import logging
import imaplib
import email
import time
from pathlib import Path
from typing import List, Optional
from email.message import Message

from ..core.config import Config
from ..services.orchestrator import Orchestrator
from ..utils.file_ops import ensure_dir

logger = logging.getLogger(__name__)


class EmailPoller:
    """Поллер для получения документов из email"""

    def __init__(self, config: Config):
        """
        Инициализация поллера

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.orchestrator = Orchestrator(config)
        self.allowed_senders = self._parse_allowed_senders()
        self.mail: Optional[imaplib.IMAP4_SSL] = None

    def _parse_allowed_senders(self) -> List[str]:
        """
        Парсинг списка разрешенных отправителей

        Returns:
            Список email адресов разрешенных отправителей
        """
        if not self.config.email_allowed_senders:
            logger.warning("No allowed senders configured for email poller")
            return []

        senders = [
            sender.strip().lower()
            for sender in self.config.email_allowed_senders.split(',')
            if sender.strip()
        ]

        logger.info(f"Allowed senders: {senders}")
        return senders

    def _is_authorized_sender(self, sender: str) -> bool:
        """
        Проверка авторизации отправителя

        Args:
            sender: Email адрес отправителя

        Returns:
            True если отправитель авторизован
        """
        # Если список пуст, разрешаем всем (небезопасно!)
        if not self.allowed_senders:
            logger.warning("No sender restrictions - allowing all senders")
            return True

        sender = sender.lower()

        # Извлечение email из формата "Name <email@example.com>"
        if '<' in sender and '>' in sender:
            start = sender.find('<') + 1
            end = sender.find('>')
            sender = sender[start:end]

        return sender in self.allowed_senders

    def connect(self):
        """Подключение к email серверу"""
        try:
            logger.info(f"Connecting to {self.config.email_host}:{self.config.email_port}")

            if self.config.email_use_ssl:
                self.mail = imaplib.IMAP4_SSL(
                    self.config.email_host,
                    self.config.email_port
                )
            else:
                self.mail = imaplib.IMAP4(
                    self.config.email_host,
                    self.config.email_port
                )

            self.mail.login(
                self.config.email_login,
                self.config.email_password
            )

            logger.info("Connected to email server")

        except Exception as e:
            logger.error(f"Failed to connect to email: {e}", exc_info=True)
            raise

    def disconnect(self):
        """Отключение от email сервера"""
        try:
            if self.mail:
                self.mail.close()
                self.mail.logout()
                logger.info("Disconnected from email server")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")

    def process_new_emails(self):
        """Обработка новых писем"""
        try:
            # Выбор папки INBOX
            self.mail.select('INBOX')

            # Поиск непрочитанных писем
            status, messages = self.mail.search(None, 'UNSEEN')

            if status != 'OK':
                logger.error("Failed to search emails")
                return

            email_ids = messages[0].split()

            if not email_ids:
                logger.debug("No new emails")
                return

            logger.info(f"Found {len(email_ids)} new email(s)")

            for email_id in email_ids:
                try:
                    self._process_email(email_id)
                except Exception as e:
                    logger.error(f"Failed to process email {email_id}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Failed to process emails: {e}", exc_info=True)

    def _process_email(self, email_id: bytes):
        """
        Обработка одного письма

        Args:
            email_id: ID письма
        """
        try:
            # Получение письма
            status, msg_data = self.mail.fetch(email_id, '(RFC822)')

            if status != 'OK':
                logger.error(f"Failed to fetch email {email_id}")
                return

            # Парсинг письма
            email_body = msg_data[0][1]
            message = email.message_from_bytes(email_body)

            # Проверка отправителя
            sender = message['From']
            logger.info(f"Processing email from: {sender}")

            if not self._is_authorized_sender(sender):
                logger.warning(f"Unauthorized sender: {sender}")
                return

            # Обработка вложений
            attachments = self._extract_attachments(message)

            if not attachments:
                logger.info("No attachments found in email")
                return

            logger.info(f"Found {len(attachments)} attachment(s)")

            # Обработка каждого вложения
            for attachment_path in attachments:
                try:
                    result = self.orchestrator.process_document(attachment_path)

                    if result["success"]:
                        logger.info(f"Successfully processed: {attachment_path}")
                    else:
                        logger.error(f"Failed to process: {attachment_path}")

                    # Очистка временного файла
                    attachment_path.unlink(missing_ok=True)

                except Exception as e:
                    logger.error(f"Failed to process attachment: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Failed to process email: {e}", exc_info=True)

    def _extract_attachments(self, message: Message) -> List[Path]:
        """
        Извлечение вложений из письма

        Args:
            message: Email сообщение

        Returns:
            Список путей к сохраненным вложениям
        """
        attachments = []

        # Директория для временных вложений
        temp_dir = self.config.temp_dir / "email_attachments"
        ensure_dir(temp_dir)

        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue

            if part.get('Content-Disposition') is None:
                continue

            filename = part.get_filename()

            if not filename:
                continue

            # Проверка расширения
            file_ext = Path(filename).suffix.lower()
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']

            if file_ext not in allowed_extensions:
                logger.debug(f"Skipping unsupported file: {filename}")
                continue

            # Сохранение вложения
            try:
                filepath = temp_dir / filename
                with open(filepath, 'wb') as f:
                    f.write(part.get_payload(decode=True))

                attachments.append(filepath)
                logger.info(f"Extracted attachment: {filename}")

            except Exception as e:
                logger.error(f"Failed to extract attachment {filename}: {e}")

        return attachments

    def run(self):
        """Запуск поллера"""
        logger.info("Starting email poller")
        logger.info(f"Poll interval: {self.config.email_poll_interval} seconds")

        while True:
            try:
                # Подключение
                self.connect()

                # Обработка новых писем
                self.process_new_emails()

                # Отключение
                self.disconnect()

                # Пауза
                logger.debug(f"Sleeping for {self.config.email_poll_interval} seconds")
                time.sleep(self.config.email_poll_interval)

            except KeyboardInterrupt:
                logger.info("Stopping email poller (Ctrl+C)")
                break

            except Exception as e:
                logger.error(f"Email poller error: {e}", exc_info=True)
                retry_delay = self.config.email_poll_retry_delay
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        # Финальная очистка
        self.disconnect()
        logger.info("Email poller stopped")


def main():
    """Точка входа для email поллера"""
    try:
        config = Config.load()
        poller = EmailPoller(config)
        poller.run()
    except Exception as e:
        logger.error(f"Email poller failed: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
