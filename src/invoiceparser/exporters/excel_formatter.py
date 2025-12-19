"""
Общий модуль форматирования данных для экспорта в Excel/Google Sheets
Содержит единую логику форматирования header и items данных
"""
import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


class ExcelFormatter:
    """
    Класс для форматирования данных для экспорта в Excel/Google Sheets
    Единая логика для локального и онлайн экспорта
    """

    @staticmethod
    def _extract_value(field_value: Any) -> Any:
        """Extract value from {_label, value} structure or return as is"""
        if isinstance(field_value, dict) and 'value' in field_value:
            return field_value['value']
        return field_value

    @staticmethod
    def _extract_label(field_value: Any, default_key: str = None) -> Optional[str]:
        """Extract label from {_label, value} structure or return default"""
        if isinstance(field_value, dict) and '_label' in field_value:
            label = field_value.get('_label')
            if label:
                return label
        return default_key

    @staticmethod
    def format_header_data(data: Dict[str, Any]) -> List[Tuple[str, str]]:
        """
        Форматирование данных заголовка в единый формат

        Возвращает список кортежей (field_name, value) в том же порядке,
        что и локальный Excel экспорт

        Args:
            data: Структурированные данные документа

        Returns:
            Список кортежей (field_name, value) для экспорта
        """
        rows = []

        # 1. Document info section
        doc_info = data.get('document_info', {})
        if doc_info:
            # Use _label from document_info if available, otherwise use key as fallback
            section_label = doc_info.get('_label') or 'Document Information'
            rows.append(('SECTION', section_label))
            rows.append(('HEADER', 'Field'))
            rows.append(('HEADER', 'Value'))

            # Process all fields in document_info
            for key, field_value in doc_info.items():
                if key == '_label':
                    continue
                value = ExcelFormatter._extract_value(field_value)
                label = ExcelFormatter._extract_label(field_value, key.replace('_', ' ').title())
                if value is not None:
                    rows.append(('FIELD', label, str(value)))

        rows.append(('EMPTY', ''))

        # 2. Parties section - iterate over all parties
        parties = data.get('parties', {})
        for party_key, party_data in parties.items():
            if not isinstance(party_data, dict):
                continue

            # Use _label from party data if available
            section_label = party_data.get('_label') or party_key.replace('_', ' ').title()
            rows.append(('SECTION', section_label))

            # Process all fields in party data
            for field_key, field_value in party_data.items():
                if field_key == '_label':
                    continue
                value = ExcelFormatter._extract_value(field_value)
                label = ExcelFormatter._extract_label(field_value, field_key.replace('_', ' ').title())
                if value is not None:
                    rows.append(('FIELD', label, str(value)))

            rows.append(('EMPTY', ''))

        # 3. References section
        references = data.get('references', {})
        if references:
            rows.append(('SECTION', 'References'))

            for ref_key, ref_value in references.items():
                value = ExcelFormatter._extract_value(ref_value)
                label = ExcelFormatter._extract_label(ref_value, ref_key.replace('_', ' ').title())
                if value is not None:
                    rows.append(('FIELD', label, str(value)))

            rows.append(('EMPTY', ''))

        # 4. Totals section
        totals = data.get('totals', {})
        if totals:
            rows.append(('SECTION', 'Totals'))

            for total_key, total_value in totals.items():
                value = ExcelFormatter._extract_value(total_value)
                label = ExcelFormatter._extract_label(total_value, total_key.replace('_', ' ').title())
                if value is not None:
                    rows.append(('FIELD', label, str(value)))

        return rows

    @staticmethod
    def format_items_data(data: Dict[str, Any]) -> Tuple[List[str], List[List[Any]]]:
        """
        Форматирование данных позиций для экспорта

        Args:
            data: Структурированные данные документа

        Returns:
            Кортеж (headers, rows) где headers - список названий колонок,
            rows - список строк данных
        """
        table_data = data.get('table_data', {})
        line_items = table_data.get('line_items', [])
        column_mapping = table_data.get('column_mapping', {})

        if not line_items:
            return [], []

        # Определяем колонки на основе column_mapping и данных
        all_keys = set()
        for item in line_items:
            all_keys.update(item.keys())

        # Sort keys: standard order first, then others
        # Note: column_mapping keys are dynamically generated by LLM per document
        standard_order = ['no', 'line_number', 'name', 'product', 'sku', 'unit',
                        'quantity', 'price', 'amount',
                        'vat_rate', 'vat_amount', 'ukt_zed']
        ordered_keys = []
        for key in standard_order:
            if key in all_keys:
                ordered_keys.append(key)
        for key in sorted(all_keys):
            if key not in ordered_keys and key not in ['raw', '_meta', '_label']:
                ordered_keys.append(key)

        # Form headers using column_mapping (contains original labels from document)
        headers = []
        for key in ordered_keys:
            # Use column_mapping which contains original labels from document
            header_text = column_mapping.get(key, key.replace('_', ' ').title())
            headers.append(header_text)

        # Формируем строки данных
        rows = []
        for item in line_items:
            row = []
            for key in ordered_keys:
                value = item.get(key)
                if value is not None:
                    # Для числовых значений сохраняем как число
                    if isinstance(value, (int, float)):
                        row.append(value)
                    else:
                        row.append(str(value))
                else:
                    row.append('')
            rows.append(row)

        return headers, rows

