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
            # Извлечение данных
            # Поддерживаем как старый формат (header/items), так и новый структурированный (document_info/parties/table_data)
            header = {}
            items = []

            # Проверяем новый структурированный формат
            if 'document_info' in approved_data or 'parties' in approved_data or 'table_data' in approved_data:
                # Новый формат - извлекаем данные из структурированного JSON
                header = self._extract_header_from_structured_data(approved_data)

                # Извлекаем items из table_data.line_items
                table_data = approved_data.get('table_data', {})
                items_raw = table_data.get('line_items', [])
                column_mapping = table_data.get('column_mapping', {})

                # Преобразуем items в стандартный формат
                for item in items_raw:
                    mapped_item = self._map_item_for_sheets(item, column_mapping)
                    items.append(mapped_item)
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

            # Сохраняем items в отдельный лист
            await self._save_items_sheet(header, items)

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

        Args:
            header: Данные заголовка
            approved_data: Полные данные документа (для структурированного формата)
        """
        sheet_name = self.config.sheets_header_sheet
        worksheet = await self._get_or_create_worksheet(sheet_name)

        # Проверяем, есть ли заголовки (если лист пустой, добавляем)
        existing_values = worksheet.get_all_values()
        if not existing_values or len(existing_values) == 0:
            # Добавляем заголовки колонок
            worksheet.append_row(['Поле', 'Значение'])
            # Форматируем первую строку как заголовок
            worksheet.format('A1:B1', {
                'backgroundColor': {'red': 0.21, 'green': 0.38, 'blue': 0.57},
                'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}
            })

        # Подготавливаем данные для сохранения
        rows_to_append = []

        # Если есть структурированные данные, используем их
        if 'document_info' in approved_data or 'parties' in approved_data:
            # Информация о документе
            doc_info = approved_data.get('document_info', {})
            if doc_info:
                rows_to_append.append(['Тип документа', doc_info.get('document_type', '')])
                rows_to_append.append(['Номер документа', doc_info.get('document_number', '')])
                rows_to_append.append(['Дата документа', doc_info.get('document_date', '')])
                rows_to_append.append(['Дата (нормалізована)', doc_info.get('document_date_normalized', '')])
                rows_to_append.append(['Місце складання', doc_info.get('location', '')])
                rows_to_append.append(['Валюта', doc_info.get('currency', '')])
                rows_to_append.append(['', ''])  # Пустая строка

            # Поставщик
            parties = approved_data.get('parties', {})
            supplier = parties.get('supplier', {})
            if supplier:
                rows_to_append.append(['Постачальник', ''])
                rows_to_append.append(['  Назва', supplier.get('name', '')])
                rows_to_append.append(['  Адреса', supplier.get('address', '')])
                rows_to_append.append(['  Телефон', supplier.get('phone', '')])
                rows_to_append.append(['  ЄДРПОУ', supplier.get('tax_id', '')])
                rows_to_append.append(['  ІПН', supplier.get('vat_id', '')])
                rows_to_append.append(['  Номер рахунку', supplier.get('account_number', '')])
                rows_to_append.append(['  Банк', supplier.get('bank', '')])
                rows_to_append.append(['', ''])  # Пустая строка

            # Покупатель
            customer = parties.get('customer', {})
            if customer:
                rows_to_append.append(['Покупець', ''])
                rows_to_append.append(['  Назва', customer.get('name', '')])
                rows_to_append.append(['  Адреса', customer.get('address', '')])
                rows_to_append.append(['  ЄДРПОУ', customer.get('tax_id', '')])
                rows_to_append.append(['  ІПН', customer.get('vat_id', '')])
                rows_to_append.append(['', ''])  # Пустая строка

            # Договір та замовлення
            references = approved_data.get('references', {})
            if references:
                rows_to_append.append(['Договір та замовлення', ''])
                if 'contract' in references and references['contract'].get('value'):
                    rows_to_append.append(['  Договір', references['contract']['value']])
                if 'order' in references and references['order'].get('value'):
                    rows_to_append.append(['  Замовлення', references['order']['value']])
                rows_to_append.append(['', ''])  # Пустая строка

            # Підсумки
            totals = approved_data.get('totals', {})
            if totals:
                rows_to_append.append(['Підсумки', ''])
                if totals.get('subtotal'):
                    rows_to_append.append(['  Сума без ПДВ', totals.get('subtotal')])
                if totals.get('vat'):
                    rows_to_append.append(['  ПДВ', totals.get('vat')])
                if totals.get('total'):
                    rows_to_append.append(['  Всього', totals.get('total')])
        else:
            # Старый формат - просто выводим все поля header
            for key, value in header.items():
                if value is not None:
                    rows_to_append.append([key, str(value)])

        if rows_to_append:
            worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            logger.info(f"✅ Saved header data to Google Sheets (sheet: {sheet_name})")

    async def _save_items_sheet(self, header: Dict[str, Any], items: List[Dict[str, Any]]):
        """
        Сохранение позиций в лист "Позиции"

        Args:
            header: Данные заголовка документа
            items: Список позиций
        """
        sheet_name = self.config.sheets_items_sheet
        worksheet = await self._get_or_create_worksheet(sheet_name)

        # Проверяем, есть ли заголовки (если лист пустой, добавляем)
        existing_values = worksheet.get_all_values()
        if not existing_values or len(existing_values) == 0:
            await self._add_items_headers(worksheet)

        # Подготовка строк для вставки
        rows_to_append = []

        for item in items:
            row = self._format_item_row(header, item)
            rows_to_append.append(row)

        if not rows_to_append:
            logger.warning("No items to save to Google Sheets")
            return

        # Добавляем данные в лист
        worksheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
        logger.info(f"✅ Saved {len(rows_to_append)} rows to Google Sheets (sheet: {sheet_name})")

    async def _add_items_headers(self, worksheet):
        """
        Добавление заголовков в лист позиций

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
        # Форматируем первую строку как заголовок
        worksheet.format('A1:S1', {
            'backgroundColor': {'red': 0.21, 'green': 0.38, 'blue': 0.57},
            'textFormat': {'bold': True, 'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0}}
        })
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

    def _extract_header_from_structured_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение данных заголовка из структурированного JSON

        Args:
            data: Структурированные данные документа

        Returns:
            Словарь с данными заголовка в стандартном формате
        """
        header = {}

        # Информация о документе
        doc_info = data.get('document_info', {})
        header['document_number'] = doc_info.get('document_number')
        header['date'] = doc_info.get('document_date') or doc_info.get('document_date_normalized')
        header['currency'] = doc_info.get('currency')

        # Поставщик
        parties = data.get('parties', {})
        supplier = parties.get('supplier', {})
        header['supplier_name'] = supplier.get('name')
        header['supplier_inn'] = supplier.get('tax_id') or supplier.get('vat_id')

        # Покупатель
        customer = parties.get('customer', {})
        header['buyer_name'] = customer.get('name')
        header['buyer_inn'] = customer.get('tax_id') or customer.get('vat_id')

        # П totals
        totals = data.get('totals', {})
        header['total_amount'] = totals.get('total')
        header['total_vat'] = totals.get('vat')

        # Альтернативные имена для совместимости
        header['invoice_number'] = header.get('document_number')
        header['document_date'] = header.get('date')

        return header

    def _map_item_for_sheets(self, item: Dict[str, Any], column_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Преобразование item из table_data в стандартный формат для Google Sheets

        Args:
            item: Исходный item из line_items
            column_mapping: Маппинг колонок

        Returns:
            Преобразованный item
        """
        mapped = {}

        # Стандартные маппинги
        field_mappings = {
            'tovar': 'name',
            'product_name': 'name',
            'product': 'name',
            'наименование': 'name',
            'товар': 'name',
            'no': 'line_number',
            'number': 'line_number',
            'номер': 'line_number',
            'kilkist': 'quantity',
            'quantity': 'quantity',
            'количество': 'quantity',
            'tsina': 'price',
            'tsina_bez_pdv': 'price',
            'price': 'price',
            'цена': 'price',
            'suma': 'amount',
            'suma_bez_pdv': 'amount',
            'amount': 'amount',
            'сумма': 'amount',
            'sku': 'sku',
            'артикул': 'sku',
            'unit': 'unit',
            'единица': 'unit',
            'vat': 'vat_rate',
            'nds': 'vat_rate',
            'пдв': 'vat_rate',
        }

        # Преобразуем поля
        for key, value in item.items():
            if key in ['raw', '_meta']:
                continue

            normalized_key = field_mappings.get(key.lower(), key)

            # Обрабатываем числовые поля
            if normalized_key in ['quantity', 'price', 'amount', 'vat_amount']:
                mapped[normalized_key] = self._parse_numeric_value(value)
            elif normalized_key == 'line_number':
                mapped[normalized_key] = self._parse_integer_value(value)
            elif normalized_key in ['name', 'sku', 'unit', 'vat_rate']:
                mapped[normalized_key] = str(value) if value is not None else None
            else:
                # Сохраняем оригинальное поле
                mapped[key] = value

        # Убеждаемся, что есть обязательное поле name
        if 'name' not in mapped:
            for possible_name_field in ['tovar', 'product_name', 'product', 'наименование', 'товар']:
                if possible_name_field in mapped:
                    mapped['name'] = str(mapped.pop(possible_name_field))
                    break

        if 'name' not in mapped:
            # Ищем первое текстовое поле
            for key, value in item.items():
                if isinstance(value, str) and value.strip() and key not in ['raw']:
                    mapped['name'] = str(value)
                    break

        if 'name' not in mapped:
            mapped['name'] = 'Unknown'

        return mapped

    def _parse_numeric_value(self, value: Any) -> Optional[float]:
        """Парсинг числового значения"""
        if value is None:
            return None

        if isinstance(value, (int, float, Decimal)):
            return float(value)

        if isinstance(value, str):
            import re
            match = re.search(r'[\d.,]+', value.replace(',', '.'))
            if match:
                try:
                    return float(match.group().replace(',', '.'))
                except (ValueError, TypeError):
                    pass

        return None

    def _parse_integer_value(self, value: Any) -> Optional[int]:
        """Парсинг целого числа"""
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, (float, Decimal)):
            return int(value)

        if isinstance(value, str):
            import re
            match = re.search(r'\d+', value)
            if match:
                try:
                    return int(match.group())
                except (ValueError, TypeError):
                    pass

        return None

