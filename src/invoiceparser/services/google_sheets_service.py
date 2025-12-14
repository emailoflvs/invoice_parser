"""
Сервис для работы с Google Sheets API
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from decimal import Decimal

from ..core.config import Config
from .invoice_data_transformer import InvoiceDataTransformer
from ..exporters.excel_formatter import ExcelFormatter

logger = logging.getLogger(__name__)

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
            # Извлечение данных с использованием общего трансформера
            header = {}
            items = []

            # Проверяем новый структурированный формат
            if 'document_info' in approved_data or 'parties' in approved_data or 'table_data' in approved_data:
                # Новый формат - используем трансформер
                header = InvoiceDataTransformer.extract_header_from_structured_data(approved_data)
                items, _ = InvoiceDataTransformer.extract_items_from_structured_data(approved_data)
            else:
                # Старый формат - используем header и items напрямую
                if hasattr(approved_data.get('header'), 'model_dump'):
                    header = approved_data.get('header').model_dump()
                else:
                    header = approved_data.get('header', {})

                items_raw = approved_data.get('items', [])
                for item in items_raw:
                    if hasattr(item, 'model_dump'):
                        items.append(item.model_dump())
                    else:
                        items.append(item)

            # Сохраняем header в отдельный лист
            await self._save_header_sheet(header, approved_data)

            # Сохраняем items в отдельный лист (передаем полные данные для форматтера)
            await self._save_items_sheet(header, items, approved_data)

            return True

        except Exception as e:
            logger.error(f"Failed to save to Google Sheets: {e}", exc_info=True)
            return False

    async def _get_or_create_worksheet(self, sheet_name: str) -> Any:
        """
        Получение или создание листа в Google Sheets

        Args:
            sheet_name: Название листа

        Returns:
            Рабочий лист
        """
        try:
            worksheet = self._spreadsheet.worksheet(sheet_name)
            return worksheet
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
                return worksheet
            else:
                # Другая ошибка - пробрасываем дальше
                raise

    async def _save_header_sheet(self, header: Dict[str, Any], approved_data: Dict[str, Any]):
        """
        Сохранение данных заголовка в лист "Реквизиты"
        Использует ту же логику форматирования, что и локальный Excel

        Args:
            header: Данные заголовка
            approved_data: Полные данные документа (для структурированного формата)
        """
        sheet_name = self.config.sheets_header_sheet
        worksheet = await self._get_or_create_worksheet(sheet_name)

        # Проверяем, есть ли заголовки (если лист пустой, добавляем)
        existing_values = worksheet.get_all_values()
        is_empty = not existing_values or len(existing_values) == 0

        # Используем общий форматтер для единообразия с локальным Excel
        if 'document_info' in approved_data or 'parties' in approved_data:
            formatted_rows = ExcelFormatter.format_header_data(approved_data)
        else:
            # Старый формат - просто выводим все поля header
            formatted_rows = []
            for key, value in header.items():
                if value is not None:
                    formatted_rows.append(('FIELD', key, str(value)))

        # Преобразуем форматированные строки в формат для Google Sheets
        rows_to_append = []
        header_added = not is_empty  # Если лист не пустой, заголовки уже есть
        header_parts = []  # Для сбора обеих частей заголовка

        for row_type, *row_data in formatted_rows:
            if row_type == 'SECTION':
                # Секция - в Google Sheets это одна строка с названием секции в первой колонке
                rows_to_append.append([row_data[0], ''])
            elif row_type == 'HEADER':
                # Заголовки колонок - собираем обе части
                # ExcelFormatter возвращает два отдельных HEADER: ('HEADER', 'Поле') и ('HEADER', 'Значение')
                if is_empty and not header_added:
                    header_parts.append(row_data[0] if row_data else '')
                    # Когда собрали обе части, добавляем строку заголовка
                    if len(header_parts) == 2:
                        rows_to_append.append([header_parts[0], header_parts[1]])
                        header_added = True
                        header_parts = []
            elif row_type == 'FIELD':
                # Поле данных
                field_name, value = row_data[0], row_data[1]
                # Преобразуем все значения в строки для единообразия
                rows_to_append.append([str(field_name) if field_name else '', str(value) if value else ''])
            elif row_type == 'EMPTY':
                # Пустая строка
                rows_to_append.append(['', ''])

        if rows_to_append:
            worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')

            # Форматируем заголовки, если они были добавлены
            if is_empty and header_added:
                # Находим строку с заголовками (первая строка после секции "Інформація про документ")
                header_row = 2  # После секции идет заголовок
                header_range = f'A{header_row}:B{header_row}'
                worksheet.format(header_range, {
                    'backgroundColor': {'red': 0.21, 'green': 0.38, 'blue': 0.57},
                    'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}
                })

            logger.info(f"✅ Saved header data to Google Sheets (sheet: {sheet_name})")

    async def _save_items_sheet(self, header: Dict[str, Any], items: List[Dict[str, Any]], approved_data: Dict[str, Any]):
        """
        Сохранение позиций в лист "Позиции"
        Использует ту же логику форматирования, что и локальный Excel

        Args:
            header: Данные заголовка документа
            items: Список позиций (уже преобразованные через трансформер)
            approved_data: Полные данные документа (для получения column_mapping)
        """
        sheet_name = self.config.sheets_items_sheet
        worksheet = await self._get_or_create_worksheet(sheet_name)

        # Проверяем, есть ли заголовки (если лист пустой, добавляем)
        existing_values = worksheet.get_all_values()
        is_empty = not existing_values or len(existing_values) == 0

        if not items:
            logger.warning("No items to save to Google Sheets")
            return

        # Используем общий форматтер для items
        # Берем оригинальные данные из approved_data (как в локальном Excel)
        # НЕ используем преобразованные items, а берем напрямую из table_data
        table_data = approved_data.get('table_data', {})
        if not table_data or 'line_items' not in table_data:
            logger.warning("No table_data.line_items found in approved_data")
            return

        # Используем оригинальные line_items и column_mapping из approved_data
        data_for_formatter = {'table_data': table_data}
        headers, rows = ExcelFormatter.format_items_data(data_for_formatter)

        if not headers or not rows:
            logger.warning("No formatted items data to save")
            return

        # Если лист пустой, добавляем заголовки
        if is_empty:
            worksheet.append_row(headers)
            # Форматируем заголовки
            import gspread.utils
            header_range = f'A1:{gspread.utils.get_column_letter(len(headers))}1'
            worksheet.format(header_range, {
                'backgroundColor': {'red': 0.21, 'green': 0.38, 'blue': 0.57},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}
            })

        # Добавляем данные
        # Преобразуем все значения в строки, чтобы избежать неправильной интерпретации типов
        # (например, Google Sheets может интерпретировать числа как даты)
        rows_as_strings = []
        for row in rows:
            row_as_strings = []
            for value in row:
                if value is None:
                    row_as_strings.append('')
                elif isinstance(value, (int, float)):
                    # Для чисел сохраняем как строку, чтобы Google Sheets не интерпретировал их как даты
                    row_as_strings.append(str(value))
                else:
                    row_as_strings.append(str(value))
            rows_as_strings.append(row_as_strings)

        worksheet.append_rows(rows_as_strings, value_input_option='USER_ENTERED')
        logger.info(f"✅ Saved {len(rows)} rows to Google Sheets (sheet: {sheet_name})")


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


