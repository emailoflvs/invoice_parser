"""
Сервис для экспорта утвержденных данных
Управляет экспортом в различные форматы (Excel, Google Sheets и т.д.)
"""
import logging
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal

from ..core.config import Config
from ..core.models import InvoiceData, InvoiceHeader, DocumentItem

logger = logging.getLogger(__name__)


class ApprovedDataExportService:
    """Сервис для экспорта утвержденных данных в различные форматы"""

    def __init__(self, config: Config):
        """
        Инициализация сервиса экспорта

        Args:
            config: Конфигурация приложения
        """
        self.config = config

        # Инициализация Excel экспортера (локальный)
        self.excel_exporter = None
        if config.export_local_excel_enabled:
            try:
                from ..exporters.excel_exporter import ExcelExporter
                self.excel_exporter = ExcelExporter(config)
                logger.info("Excel exporter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Excel exporter: {e}")
                self.excel_exporter = None

        # Инициализация Google Sheets сервиса (онлайн Excel)
        self.sheets_service = None
        if config.export_online_excel_enabled:
            try:
                from ..services.google_sheets_service import GoogleSheetsService
                self.sheets_service = GoogleSheetsService(config)
                if self.sheets_service.is_enabled():
                    logger.info("Google Sheets service initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Sheets service: {e}")
                self.sheets_service = None

    async def export_approved_data(
        self,
        approved_data: Dict[str, Any],
        original_filename: Optional[str] = None,
        export_formats: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Экспорт утвержденных данных во все включенные форматы

        Args:
            approved_data: Утвержденные данные документа (dict)
            original_filename: Оригинальное имя файла (для генерации имен выходных файлов)
            export_formats: Список форматов для экспорта (None = все включенные форматы)
                          Возможные значения: ['excel', 'sheets']

        Returns:
            Словарь с результатами экспорта:
            {
                'excel': {'success': bool, 'path': Optional[Path], 'error': Optional[str]},
                'sheets': {'success': bool, 'error': Optional[str]}
            }
        """
        results = {
            'excel': {'success': False, 'path': None, 'error': None},
            'sheets': {'success': False, 'error': None}
        }

        # Если не указаны форматы, используем все включенные
        if export_formats is None:
            export_formats = []
            if self.config.export_local_excel_enabled and self.excel_exporter:
                export_formats.append('excel')
            if self.config.export_online_excel_enabled and self.sheets_service and self.sheets_service.is_enabled():
                export_formats.append('sheets')

        # Экспорт в Excel
        if 'excel' in export_formats and self.excel_exporter:
            try:
                excel_result = await self._export_to_excel(approved_data, original_filename)
                results['excel'] = excel_result
            except Exception as e:
                logger.error(f"Failed to export to Excel: {e}", exc_info=True)
                results['excel'] = {
                    'success': False,
                    'path': None,
                    'error': str(e)
                }

        # Экспорт в Google Sheets
        if 'sheets' in export_formats and self.sheets_service:
            try:
                sheets_result = await self._export_to_sheets(approved_data)
                results['sheets'] = sheets_result
            except Exception as e:
                logger.error(f"Failed to export to Google Sheets: {e}", exc_info=True)
                results['sheets'] = {
                    'success': False,
                    'error': str(e)
                }

        return results

    async def _export_to_excel(
        self,
        approved_data: Dict[str, Any],
        original_filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Экспорт утвержденных данных в Excel

        Args:
            approved_data: Утвержденные данные
            original_filename: Оригинальное имя файла

        Returns:
            Результат экспорта
        """
        try:
            # Преобразуем dict в InvoiceData для Excel экспорта
            invoice_data_model = self._convert_to_invoice_data(approved_data)

            # Создаем путь для экспорта (используем оригинальное имя файла)
            if original_filename:
                original_path = Path(original_filename)
            else:
                # Генерируем имя на основе данных
                document_number = approved_data.get('header', {}).get('invoice_number') or \
                                approved_data.get('header', {}).get('document_number') or \
                                'document'
                original_path = Path(f"{document_number}.xlsx")

            # Экспортируем в Excel (передаем raw_data для структурированного экспорта)
            excel_path = self.excel_exporter.export(original_path, invoice_data_model, raw_data=approved_data)
            logger.info(f"✅ APPROVED data exported to Excel: {excel_path}")

            return {
                'success': True,
                'path': excel_path,
                'error': None
            }
        except Exception as e:
            logger.error(f"Excel export failed: {e}", exc_info=True)
            return {
                'success': False,
                'path': None,
                'error': str(e)
            }

    async def _export_to_sheets(self, approved_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Экспорт утвержденных данных в Google Sheets

        Args:
            approved_data: Утвержденные данные

        Returns:
            Результат экспорта
        """
        try:
            success = await self.sheets_service.save_approved_document(approved_data)
            if success:
                logger.info(f"✅ APPROVED data exported to Google Sheets")
                return {
                    'success': True,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'error': 'Google Sheets service returned False'
                }
        except Exception as e:
            logger.error(f"Google Sheets export failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    def _convert_to_invoice_data(self, approved_data: Dict[str, Any]) -> InvoiceData:
        """
        Преобразование dict в InvoiceData модель

        Args:
            approved_data: Утвержденные данные в формате dict

        Returns:
            InvoiceData модель
        """
        # Извлекаем header данные
        header_data = approved_data.get('header', {})
        if not header_data:
            # Если нет header, пытаемся извлечь из корня
            header_data = {
                k: v for k, v in approved_data.items()
                if k not in ['items', 'table_data', 'test_results', '_meta', 'document_id']
            }

        # Создаем InvoiceHeader
        invoice_header = InvoiceHeader(**header_data)

        # Извлекаем items
        items_list = []
        column_mapping = {}

        if 'items' in approved_data:
            items_list = approved_data['items']
        elif 'table_data' in approved_data:
            if 'line_items' in approved_data['table_data']:
                items_list = approved_data['table_data']['line_items']
            if 'column_mapping' in approved_data['table_data']:
                column_mapping = approved_data['table_data']['column_mapping']

        # Преобразуем items в DocumentItem
        document_items = []
        for item in items_list:
            if isinstance(item, dict):
                # Преобразуем поля согласно column_mapping
                mapped_item = self._map_item_fields(item, column_mapping)
                # Используем extra="allow" для поддержки дополнительных полей
                try:
                    document_items.append(DocumentItem(**mapped_item))
                except Exception as e:
                    # Если не удалось создать DocumentItem, пытаемся с минимальными полями
                    logger.warning(f"Failed to create DocumentItem from {item}: {e}")
                    # Создаем с обязательным полем name
                    if 'name' not in mapped_item and 'tovar' in mapped_item:
                        mapped_item['name'] = str(mapped_item.get('tovar', 'Unknown'))
                    if 'name' not in mapped_item:
                        mapped_item['name'] = 'Unknown'
                    document_items.append(DocumentItem(**mapped_item))

        # Создаем InvoiceData
        return InvoiceData(
            header=invoice_header,
            items=document_items
        )

    def _map_item_fields(self, item: Dict[str, Any], column_mapping: Dict[str, str]) -> Dict[str, Any]:
        """
        Преобразование полей item согласно column_mapping

        Args:
            item: Исходный item из line_items
            column_mapping: Маппинг колонок (например, {"tovar": "Товар", "name": "Наименование"})

        Returns:
            Преобразованный item с нормализованными именами полей
        """
        mapped = {}

        # Обратный маппинг: ищем нормализованные ключи по значениям column_mapping
        reverse_mapping = {v: k for k, v in column_mapping.items()}

        # Стандартные маппинги для общих полей
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
            'price': 'price',
            'цена': 'price',
            'suma': 'amount',
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
            # Пропускаем служебные поля
            if key in ['raw', '_meta']:
                continue

            # Пытаемся найти стандартный маппинг
            normalized_key = field_mappings.get(key.lower(), key)

            # Если это уже нормализованный ключ, используем его
            if normalized_key in ['name', 'line_number', 'quantity', 'price', 'amount', 'sku', 'unit', 'vat_rate', 'vat_amount']:
                # Обрабатываем числовые поля
                if normalized_key in ['quantity', 'price', 'amount', 'vat_amount']:
                    mapped[normalized_key] = self._parse_numeric_value(value)
                elif normalized_key == 'line_number':
                    mapped[normalized_key] = self._parse_integer_value(value)
                else:
                    mapped[normalized_key] = value
            else:
                # Сохраняем оригинальное поле (extra="allow" позволяет это)
                mapped[key] = value

        # Убеждаемся, что есть обязательное поле name
        if 'name' not in mapped:
            # Пытаемся найти название товара в разных полях
            for possible_name_field in ['tovar', 'product_name', 'product', 'наименование', 'товар']:
                if possible_name_field in mapped:
                    mapped['name'] = str(mapped.pop(possible_name_field))
                    break

            # Если все еще нет name, используем первое текстовое поле
            if 'name' not in mapped:
                for key, value in item.items():
                    if isinstance(value, str) and value.strip() and key not in ['raw']:
                        mapped['name'] = str(value)
                        break

            # Если совсем ничего не нашли, используем дефолтное значение
            if 'name' not in mapped:
                mapped['name'] = 'Unknown'

        return mapped

    def _parse_numeric_value(self, value: Any) -> Optional[Decimal]:
        """
        Парсинг числового значения из строки или числа

        Args:
            value: Значение для парсинга

        Returns:
            Decimal или None
        """
        if value is None:
            return None

        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value))

        if isinstance(value, str):
            # Извлекаем число из строки (например, "2 шт" -> "2")
            match = re.search(r'[\d.,]+', value.replace(',', '.'))
            if match:
                try:
                    return Decimal(match.group().replace(',', '.'))
                except (ValueError, TypeError):
                    pass

        return None

    def _parse_integer_value(self, value: Any) -> Optional[int]:
        """
        Парсинг целого числа из строки или числа

        Args:
            value: Значение для парсинга

        Returns:
            int или None
        """
        if value is None:
            return None

        if isinstance(value, int):
            return value

        if isinstance(value, (float, Decimal)):
            return int(value)

        if isinstance(value, str):
            # Извлекаем число из строки
            match = re.search(r'\d+', value)
            if match:
                try:
                    return int(match.group())
                except (ValueError, TypeError):
                    pass

        return None

