"""
Сервис для экспорта утвержденных данных
Управляет экспортом в различные форматы (Excel, Google Sheets и т.д.)
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..core.config import Config
from ..core.models import InvoiceData, InvoiceHeader, DocumentItem
from .invoice_data_transformer import InvoiceDataTransformer

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
            # original_filename уже содержит правильное имя без расширения (например: invoice_755_web_14121807)
            if original_filename:
                # Убираем расширение, если есть, и добавляем .xlsx
                # original_filename уже содержит полный формат: invoice_755_web_14121807
                original_stem = Path(original_filename).stem
                original_path = Path(f"{original_stem}.xlsx")
            else:
                # Fallback: генерируем имя на основе данных
                doc_info = approved_data.get('document_info', {}) if isinstance(approved_data, dict) else {}
                document_number = doc_info.get('document_number') or doc_info.get('invoice_number') or \
                                approved_data.get('header', {}).get('invoice_number') or \
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

        # Извлекаем items с использованием трансформера
        items_list, column_mapping = InvoiceDataTransformer.extract_items_from_structured_data(approved_data)

        # Преобразуем items в DocumentItem
        document_items = []
        for mapped_item in items_list:
            # Используем extra="allow" для поддержки дополнительных полей
            try:
                document_items.append(DocumentItem(**mapped_item))
            except Exception as e:
                # Если не удалось создать DocumentItem, пытаемся с минимальными полями
                logger.warning(f"Failed to create DocumentItem from {mapped_item}: {e}")
                # Создаем с обязательным полем name
                if 'name' not in mapped_item:
                    mapped_item['name'] = 'Unknown'
                document_items.append(DocumentItem(**mapped_item))

        # Создаем InvoiceData
        return InvoiceData(
            header=invoice_header,
            items=document_items
        )


