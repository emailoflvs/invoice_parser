"""
Сервис для работы с Google Sheets API
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from decimal import Decimal

from ..core.config import Config

logger = logging.getLogger(__name__)

# Ленивый импорт gspread
try:
    import gspread
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None


class GoogleSheetsService:
    """Сервис для сохранения данных в Google Sheets"""

    def __init__(self, config: Config):
        """
        Инициализация сервиса

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self._client = None
        self._spreadsheet = None

        if not config.export_online_excel_enabled:
            logger.info("Google Sheets (Online Excel) integration is disabled")
            return

        if not config.sheets_spreadsheet_id:
            logger.warning("SHEETS_SPREADSHEET_ID is not set, Google Sheets integration will be disabled")
            return

        if not config.sheets_credentials_path:
            logger.warning("SHEETS_CREDENTIALS_PATH is not set, Google Sheets integration will be disabled")
            return

        try:
            self._initialize_client()
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}", exc_info=True)
            self._client = None

    def _initialize_client(self):
        """Инициализация клиента Google Sheets"""
        if not GSPREAD_AVAILABLE:
            raise ImportError("gspread library is not installed. Install with: pip install gspread")

        try:
            from google.oauth2.service_account import Credentials

            credentials_path = Path(self.config.sheets_credentials_path)
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credentials file not found: {credentials_path}")

            # Загрузка credentials
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(
                str(credentials_path),
                scopes=scopes
            )

            # Создание клиента
            self._client = gspread.authorize(credentials)

            # Открытие spreadsheet
            self._spreadsheet = self._client.open_by_key(self.config.sheets_spreadsheet_id)
            logger.info(f"✅ Google Sheets client initialized (spreadsheet_id: {self.config.sheets_spreadsheet_id})")

        except ImportError:
            logger.error("gspread or google-auth libraries not installed. Install with: pip install gspread google-auth")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}", exc_info=True)
            raise

    def is_enabled(self) -> bool:
        """
        Проверка, включен ли сервис

        Returns:
            True если сервис включен и готов к работе
        """
        return (
            self.config.export_online_excel_enabled
            and self._client is not None
            and self._spreadsheet is not None
        )

    async def save_approved_document(self, approved_data: Dict[str, Any]) -> bool:
        """
        Сохранение утвержденного документа в Google Sheets

        Args:
            approved_data: Утвержденные данные документа

        Returns:
            True если данные успешно сохранены
        """
        if not self.is_enabled():
            logger.debug("Google Sheets service is not enabled, skipping save")
            return False

        try:
            # Получение или создание листа
            sheet_name = self.config.sheets_items_sheet
            worksheet = None

            try:
                worksheet = self._spreadsheet.worksheet(sheet_name)
                # Проверяем, есть ли заголовки (если лист пустой, добавляем)
                existing_values = worksheet.get_all_values()
                if not existing_values or len(existing_values) == 0:
                    await self._add_headers(worksheet)
            except Exception as e:
                # Проверяем, что это ошибка "лист не найден"
                error_str = str(e).lower()
                error_type = type(e).__name__
                if "not found" in error_str or "WorksheetNotFound" in error_type:
                    # Создаем новый лист если его нет
                    logger.info(f"Sheet '{sheet_name}' not found, creating new sheet")
                    worksheet = self._spreadsheet.add_worksheet(
                        title=sheet_name,
                        rows=1000,
                        cols=20
                    )
                    # Добавляем заголовки
                    await self._add_headers(worksheet)
                else:
                    # Другая ошибка - пробрасываем дальше
                    raise

            # Извлечение данных
            # Поддерживаем как Pydantic модели, так и dict
            if hasattr(approved_data.get('header'), 'model_dump'):
                header = approved_data.get('header').model_dump()
            else:
                header = approved_data.get('header', {})

            items_raw = approved_data.get('items', [])
            items = []
            for item in items_raw:
                if hasattr(item, 'model_dump'):
                    items.append(item.model_dump())
                else:
                    items.append(item)

            # Подготовка строк для вставки
            rows_to_append = []

            for item in items:
                row = self._format_item_row(header, item)
                rows_to_append.append(row)

            if not rows_to_append:
                logger.warning("No items to save to Google Sheets")
                return True

            # Добавляем данные в лист
            worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            logger.info(f"✅ Saved {len(rows_to_append)} rows to Google Sheets (sheet: {sheet_name})")

            return True

        except Exception as e:
            logger.error(f"Failed to save to Google Sheets: {e}", exc_info=True)
            return False

    async def _add_headers(self, worksheet):
        """
        Добавление заголовков в лист

        Args:
            worksheet: Рабочий лист Google Sheets
        """
        headers = [
            'Дата сохранения',
            'Номер документа',
            'Дата документа',
            'Поставщик',
            'ИНН поставщика',
            'Покупатель',
            'ИНН покупателя',
            'Валюта',
            'Сумма документа',
            'НДС',
            '№ строки',
            'Наименование',
            'Артикул',
            'Единица измерения',
            'Количество',
            'Цена',
            'Сумма',
            'Ставка НДС',
            'Сумма НДС'
        ]

        # Очищаем первую строку и добавляем заголовки
        worksheet.clear()
        worksheet.append_row(headers)
        logger.info(f"Added headers to sheet: {worksheet.title}")

    def _format_item_row(self, header: Dict[str, Any], item: Dict[str, Any]) -> List[Any]:
        """
        Форматирование строки позиции для вставки в Google Sheets

        Args:
            header: Данные заголовка документа
            item: Данные позиции

        Returns:
            Список значений для строки
        """
        # Текущая дата и время сохранения
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Данные заголовка
        document_number = self._safe_get(header, ['invoice_number', 'document_number'])
        document_date = self._format_date(self._safe_get(header, ['date', 'document_date']))
        supplier_name = self._safe_get(header, ['supplier_name'])
        supplier_inn = self._safe_get(header, ['supplier_inn'])
        buyer_name = self._safe_get(header, ['buyer_name'])
        buyer_inn = self._safe_get(header, ['buyer_inn'])
        currency = self._safe_get(header, ['currency'])
        total_amount = self._format_decimal(self._safe_get(header, ['total_amount']))
        total_vat = self._format_decimal(self._safe_get(header, ['total_vat']))

        # Данные позиции
        line_number = self._safe_get(item, ['line_number'])
        name = self._safe_get(item, ['name'])
        sku = self._safe_get(item, ['sku'])
        unit = self._safe_get(item, ['unit'])
        quantity = self._format_decimal(self._safe_get(item, ['quantity']))
        price = self._format_decimal(self._safe_get(item, ['price']))
        amount = self._format_decimal(self._safe_get(item, ['amount']))
        vat_rate = self._safe_get(item, ['vat_rate'])
        vat_amount = self._format_decimal(self._safe_get(item, ['vat_amount']))

        return [
            now,
            document_number,
            document_date,
            supplier_name,
            supplier_inn,
            buyer_name,
            buyer_inn,
            currency,
            total_amount,
            total_vat,
            line_number,
            name,
            sku,
            unit,
            quantity,
            price,
            amount,
            vat_rate,
            vat_amount
        ]

    def _safe_get(self, data: Dict[str, Any], keys: List[str], default: Any = '') -> Any:
        """
        Безопасное получение значения из словаря по списку возможных ключей

        Args:
            data: Словарь данных
            keys: Список возможных ключей
            default: Значение по умолчанию

        Returns:
            Значение или default
        """
        for key in keys:
            if key in data and data[key] is not None:
                return data[key]
        return default

    def _format_date(self, value: Any) -> str:
        """
        Форматирование даты для Google Sheets

        Args:
            value: Значение даты (может быть date, datetime, str)

        Returns:
            Отформатированная строка даты
        """
        if value is None:
            return ''

        if isinstance(value, (date, datetime)):
            return value.strftime('%Y-%m-%d')
        elif isinstance(value, str):
            return value
        else:
            return str(value)

    def _format_decimal(self, value: Any) -> Any:
        """
        Форматирование Decimal для Google Sheets

        Args:
            value: Значение (может быть Decimal, float, int, str)

        Returns:
            Числовое значение или пустая строка
        """
        if value is None:
            return ''

        if isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, str):
            try:
                return float(value)
            except (ValueError, TypeError):
                return value
        else:
            return value

