"""
Трансформер данных для экспорта
Общая логика преобразования структурированных данных документа
"""
import logging
import re
from typing import Dict, Any, Optional, List
from decimal import Decimal

logger = logging.getLogger(__name__)


class InvoiceDataTransformer:
    """
    Класс для преобразования структурированных данных документа
    в стандартизированный формат для экспорта
    """

    # Стандартные маппинги полей items
    FIELD_MAPPINGS = {
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

    # Поля, которые могут содержать название товара
    POSSIBLE_NAME_FIELDS = ['tovar', 'product_name', 'product', 'наименование', 'товар']

    @staticmethod
    def extract_header_from_structured_data(data: Dict[str, Any]) -> Dict[str, Any]:
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

        # Итоги
        totals = data.get('totals', {})
        header['total_amount'] = totals.get('total')
        header['total_vat'] = totals.get('vat')

        # Альтернативные имена для совместимости
        header['invoice_number'] = header.get('document_number')
        header['document_date'] = header.get('date')

        return header

    @staticmethod
    def extract_items_from_structured_data(data: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Извлечение items из структурированных данных

        Args:
            data: Структурированные данные документа

        Returns:
            Кортеж (список items, column_mapping)
        """
        items = []
        column_mapping = {}

        # Проверяем новый структурированный формат
        if 'table_data' in data:
            table_data = data.get('table_data', {})
            items_raw = table_data.get('line_items', [])
            column_mapping = table_data.get('column_mapping', {})

            # Преобразуем items в стандартный формат
            for item in items_raw:
                if isinstance(item, dict):
                    mapped_item = InvoiceDataTransformer.map_item_fields(item, column_mapping)
                    items.append(mapped_item)
        elif 'items' in data:
            # Старый формат
            items_raw = data.get('items', [])
            for item in items_raw:
                if hasattr(item, 'model_dump'):
                    items.append(item.model_dump())
                else:
                    items.append(item)

        return items, column_mapping

    @staticmethod
    def map_item_fields(item: Dict[str, Any], column_mapping: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Преобразование полей item согласно стандартным маппингам

        Args:
            item: Исходный item из line_items
            column_mapping: Маппинг колонок (опционально, для обратной совместимости)

        Returns:
            Преобразованный item с нормализованными именами полей
        """
        if column_mapping is None:
            column_mapping = {}

        mapped = {}

        # Преобразуем поля
        for key, value in item.items():
            # Пропускаем служебные поля
            if key in ['raw', '_meta']:
                continue

            # Пытаемся найти стандартный маппинг
            normalized_key = InvoiceDataTransformer.FIELD_MAPPINGS.get(key.lower(), key)

            # Если это нормализованный ключ, обрабатываем его
            if normalized_key in ['name', 'line_number', 'quantity', 'price', 'amount', 'sku', 'unit', 'vat_rate', 'vat_amount']:
                # Обрабатываем числовые поля
                if normalized_key in ['quantity', 'price', 'amount', 'vat_amount']:
                    mapped[normalized_key] = InvoiceDataTransformer.parse_numeric_value(value, return_decimal=True)
                elif normalized_key == 'line_number':
                    mapped[normalized_key] = InvoiceDataTransformer.parse_integer_value(value)
                else:
                    mapped[normalized_key] = str(value) if value is not None else None
            else:
                # Сохраняем оригинальное поле
                mapped[key] = value

        # Убеждаемся, что есть обязательное поле name
        if 'name' not in mapped:
            # Пытаемся найти название товара в разных полях
            for possible_name_field in InvoiceDataTransformer.POSSIBLE_NAME_FIELDS:
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

    @staticmethod
    def parse_numeric_value(value: Any, return_decimal: bool = False) -> Optional[Decimal | float]:
        """
        Парсинг числового значения из строки или числа

        Args:
            value: Значение для парсинга
            return_decimal: Если True, возвращает Decimal, иначе float

        Returns:
            Decimal или float или None
        """
        if value is None:
            return None

        if isinstance(value, (int, float, Decimal)):
            if return_decimal:
                return Decimal(str(value))
            return float(value)

        if isinstance(value, str):
            # Извлекаем число из строки (например, "2 шт" -> "2")
            match = re.search(r'[\d.,]+', value.replace(',', '.'))
            if match:
                try:
                    num_str = match.group().replace(',', '.')
                    if return_decimal:
                        return Decimal(num_str)
                    return float(num_str)
                except (ValueError, TypeError):
                    pass

        return None

    @staticmethod
    def parse_integer_value(value: Any) -> Optional[int]:
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

    @staticmethod
    def get_structured_header_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Получение структурированных данных заголовка для экспорта
        (document_info, parties, references, totals)

        Args:
            data: Полные данные документа

        Returns:
            Словарь с секциями данных
        """
        return {
            'document_info': data.get('document_info', {}),
            'parties': data.get('parties', {}),
            'references': data.get('references', {}),
            'totals': data.get('totals', {}),
            'amounts_in_words': data.get('amounts_in_words', {}),
            'other_fields': data.get('other_fields', []),
        }

