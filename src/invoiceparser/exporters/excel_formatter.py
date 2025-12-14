"""
Общий модуль форматирования данных для экспорта в Excel/Google Sheets
Содержит единую логику форматирования header и items данных
"""
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

# Маппинг типов документов на украинские названия
DOCUMENT_TYPE_MAPPING = {
    'delivery_note': 'Видаткова накладна',
    'invoice': 'Рахунок-фактура',
    'waybill': 'Товарна накладна',
    'receipt': 'Квитанція',
    'act': 'Акт',
    'contract': 'Договір',
    'order': 'Замовлення',
    'bill': 'Рахунок',
    'proforma_invoice': 'Проформа-рахунок',
    'credit_note': 'Кредитна нота',
    'debit_note': 'Дебетна нота',
}


class ExcelFormatter:
    """
    Класс для форматирования данных для экспорта в Excel/Google Sheets
    Единая логика для локального и онлайн экспорта
    """

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

        # 1. Інформація про документ
        rows.append(('SECTION', 'Інформація про документ'))
        rows.append(('HEADER', 'Поле'))  # Заголовок колонок
        rows.append(('HEADER', 'Значение'))

        doc_info = data.get('document_info', {})
        if doc_info:
            # Преобразуем document_type в читаемый формат
            document_type = doc_info.get('document_type')
            if document_type and document_type in DOCUMENT_TYPE_MAPPING:
                document_type = DOCUMENT_TYPE_MAPPING[document_type]

            doc_fields = {
                'Тип документа': document_type,
                'Номер документа': doc_info.get('document_number'),
                'Дата документа': doc_info.get('document_date'),
                'Дата (нормалізована)': doc_info.get('document_date_normalized'),
                'Місце складання': doc_info.get('location'),
                'Валюта': doc_info.get('currency'),
            }
            for field_name, value in doc_fields.items():
                if value is not None:
                    rows.append(('FIELD', field_name, str(value)))

        rows.append(('EMPTY', ''))  # Пустая строка

        # 2. Постачальник
        parties = data.get('parties', {})
        supplier = parties.get('supplier', {})
        if supplier:
            rows.append(('SECTION', 'Постачальник'))

            supplier_fields = {
                'Назва': supplier.get('name'),
                'Адреса': supplier.get('address'),
                'Телефон': supplier.get('phone'),
                'ЄДРПОУ': supplier.get('tax_id'),
                'ІПН': supplier.get('vat_id'),
                'Номер рахунку': supplier.get('account_number'),
                'Банк': supplier.get('bank'),
            }
            for field_name, value in supplier_fields.items():
                if value is not None:
                    rows.append(('FIELD', field_name, str(value)))

            rows.append(('EMPTY', ''))  # Пустая строка

        # 3. Покупець
        customer = parties.get('customer', {})
        if customer:
            rows.append(('SECTION', 'Покупець'))

            customer_fields = {
                'Назва': customer.get('name'),
                'Адреса': customer.get('address'),
                'ЄДРПОУ': customer.get('tax_id'),
                'ІПН': customer.get('vat_id'),
            }
            for field_name, value in customer_fields.items():
                if value is not None:
                    rows.append(('FIELD', field_name, str(value)))

            rows.append(('EMPTY', ''))  # Пустая строка

        # 4. Договір та замовлення
        references = data.get('references', {})
        if references:
            rows.append(('SECTION', 'Договір та замовлення'))

            # Проверяем contract - может быть dict или str
            if 'contract' in references:
                contract_value = None
                if isinstance(references['contract'], dict):
                    contract_value = references['contract'].get('value')
                elif isinstance(references['contract'], str):
                    contract_value = references['contract']
                if contract_value:
                    rows.append(('FIELD', 'Договір', str(contract_value)))

            # Проверяем order - может быть dict или str
            if 'order' in references:
                order_value = None
                if isinstance(references['order'], dict):
                    order_value = references['order'].get('value')
                elif isinstance(references['order'], str):
                    order_value = references['order']
                if order_value:
                    rows.append(('FIELD', 'Замовлення', str(order_value)))

            rows.append(('EMPTY', ''))  # Пустая строка

        # 5. Підсумки
        totals = data.get('totals', {})
        if totals:
            rows.append(('SECTION', 'Підсумки'))

            totals_fields = {
                'Сума без ПДВ': totals.get('subtotal'),
                'ПДВ': totals.get('vat'),
                'Всього': totals.get('total'),
            }
            for field_name, value in totals_fields.items():
                if value is not None:
                    rows.append(('FIELD', field_name, str(value)))

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

        # Сортируем ключи: сначала стандартные, потом остальные
        standard_order = ['no', 'line_number', 'name', 'tovar', 'product', 'sku', 'unit',
                        'quantity', 'kilkist', 'price', 'tsina', 'amount', 'suma',
                        'vat_rate', 'vat_amount', 'ukt_zed']
        ordered_keys = []
        for key in standard_order:
            if key in all_keys:
                ordered_keys.append(key)
        for key in sorted(all_keys):
            if key not in ordered_keys and key not in ['raw', '_meta']:
                ordered_keys.append(key)

        # Формируем заголовки
        headers = []
        for key in ordered_keys:
            # Используем column_mapping для украинских названий
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

