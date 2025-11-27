"""
Post-процессор для преобразования сырых ответов Gemini в финальную структуру
"""
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class InvoicePostProcessor:
    """
    Класс для превращения сырых ответов Gemini в идеальную структуру Invoice
    """

    # Маппинг ключей из промпта (Items) в целевой JSON
    ITEMS_KEY_MAPPING = {
        "ROW_NUMBER": "row_number",
        "ITEM_NAME": "item_name",
        "ARTICLE_CODE": "ukt_zed_code",
        "SKU_CODE": "ukt_zed_code",
        "QUANTITY": "quantity",
        "UNIT": "unit",
        "UNIT_OF_MEASURE": "unit",
        "PRICE_SINGLE": "price_without_vat",
        "PRICE_UNIT": "price_without_vat",
        "AMOUNT_ROW": "sum_without_vat",
        "AMOUNT_TOTAL_NO_VAT": "sum_without_vat",
        "VAT_RATE": "vat_rate",
        # Украинские варианты (если модель вернет с оригинальными заголовками)
        "№": "row_number",
        "Артикул": "ukt_zed_code",
        "УКТ ЗЕД": "ukt_zed_code",
        "Товар": "item_name",
        "Продукція": "item_name",
        "Кількість": "quantity",
        "Ціна без ПДВ": "price_without_vat",
        "Сума без ПДВ": "sum_without_vat"
    }

    @staticmethod
    def clean_number_str(value: Any) -> float:
        """Конвертирует строку '10 500,00' -> 10500.0"""
        if isinstance(value, (int, float)):
            return float(value)
        if not value or not isinstance(value, str):
            return 0.0
        
        # Убираем пробелы (неразрывные и обычные)
        clean = value.replace(" ", "").replace("\u00a0", "")
        # Заменяем запятую на точку
        clean = clean.replace(",", ".")
        # Удаляем все кроме цифр и точки
        clean = re.sub(r"[^\d.]", "", clean)
        
        try:
            return float(clean) if clean else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    def clean_int_str(value: Any) -> int:
        """Конвертирует строку '2.00' или '2 шт' -> 2"""
        if isinstance(value, int):
            return value
        val_float = InvoicePostProcessor.clean_number_str(value)
        return int(val_float)

    @staticmethod
    def extract_unit_from_quantity(quantity_str: str) -> tuple[float, str]:
        """Извлекает количество и единицу измерения из '2 шт' -> (2.0, 'шт')"""
        if not isinstance(quantity_str, str):
            return (InvoicePostProcessor.clean_number_str(quantity_str), "")
        
        # Ищем число в начале строки
        match = re.match(r"([0-9\s,.]+)\s*(.+)?", quantity_str.strip())
        if match:
            num_part = match.group(1)
            unit_part = match.group(2) or ""
            return (InvoicePostProcessor.clean_number_str(num_part), unit_part.strip())
        
        return (InvoicePostProcessor.clean_number_str(quantity_str), "")

    def process(self, header_json: Dict[str, Any], items_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Главный метод объединения
        
        Args:
            header_json: Результат парсинга header.txt
            items_json: Результат парсинга items.txt
            
        Returns:
            Финальная структура Invoice
        """
        final_invoice = {}
        
        # 1. Обработка Header
        # document_info
        final_invoice["document_info"] = self._normalize_document_info(
            header_json.get("document_info", {})
        )
        
        # parties (нормализация supplier/buyer)
        final_invoice["parties"] = self._normalize_parties(
            header_json.get("parties", {})
        )
        
        # references
        final_invoice["references"] = self._normalize_references(
            header_json.get("contract_reference", {})
        )
        
        # 2. Обработка Items (трансформация таблицы)
        tables = items_json.get("tables", [])
        final_invoice["line_items"] = self._normalize_line_items(tables)
        
        # 3. Totals
        final_invoice["totals"] = self._calculate_totals(
            final_invoice["line_items"],
            header_json.get("amounts", {})
        )
        
        # 4. Amounts in words
        final_invoice["amounts_in_words"] = self._extract_amounts_in_words(
            header_json.get("other_fields", {}),
            items_json.get("fields", [])
        )
        
        # 5. Signatures (если есть)
        final_invoice["signatures"] = self._extract_signatures(
            header_json.get("other_fields", {}),
            items_json.get("fields", [])
        )
        
        return final_invoice

    def _normalize_document_info(self, doc_info: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализация информации о документе"""
        return {
            "type": doc_info.get("type", ""),
            "number": str(doc_info.get("number", "")).strip(),
            "date_raw": doc_info.get("date_raw", doc_info.get("date", "")),
            "date_iso": doc_info.get("date_iso", ""),
            "place_of_issue": doc_info.get("place_of_issue", ""),
            "currency": doc_info.get("currency", "")
        }

    def _normalize_parties(self, raw_parties: Dict[str, Any]) -> Dict[str, Any]:
        """Приводит структуру сторон к единому виду"""
        normalized = {}
        
        # Маппинг ролей
        role_map = {
            "performer": "supplier",
            "supplier": "supplier",
            "customer": "buyer",
            "buyer": "buyer"
        }
        
        for key, data in raw_parties.items():
            if not isinstance(data, dict):
                continue
                
            target_key = role_map.get(key, key)
            
            # Извлекаем данные
            name = data.get("name", data.get("full_name", ""))
            
            # details может быть dict или данные на верхнем уровне
            if "details" in data and isinstance(data["details"], dict):
                details = data["details"]
            else:
                details = data
            
            normalized[target_key] = {
                "role": data.get("role", ""),
                "name": name,
                "details": {
                    "edrpou": details.get("edrpou", details.get("tax_id", "")),
                    "ipn": details.get("ipn", details.get("vat_id", "")),
                    "bank_account": details.get("bank_account", ""),
                    "bank_name": details.get("bank_name", ""),
                    "address": details.get("address", ""),
                    "phone": details.get("phone", details.get("contact", ""))
                }
            }
        
        return normalized

    def _normalize_references(self, contract_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Нормализация ссылок на договоры/заказы"""
        contract = contract_ref.get("contract", contract_ref.get("contract_number", ""))
        order = contract_ref.get("order", contract_ref.get("order_number", ""))
        
        # Если order содержит полный текст типа "Замовлення покупця № 826 від..."
        # оставляем как есть, иначе пытаемся собрать
        if not order and contract_ref.get("order_number"):
            order_num = contract_ref.get("order_number", "")
            order_date = contract_ref.get("order_date", "")
            if order_num and order_date:
                order = f"Замовлення покупця № {order_num} від {order_date}"
            else:
                order = order_num
        
        return {
            "contract": contract,
            "order": order
        }

    def _normalize_line_items(self, tables: List) -> List[Dict[str, Any]]:
        """Превращает таблицы Gemini в плоский список товаров"""
        all_items = []
        
        # tables может быть list[list[dict]] (старый формат) или list[dict] (новый формат)
        for table in tables:
            raw_items = []
            
            # Новый формат: {"table_id": 1, "line_items": [...]}
            if isinstance(table, dict) and "line_items" in table:
                raw_items = table.get("line_items", [])
            # Старый формат: [[{...}, {...}]]
            elif isinstance(table, list):
                raw_items = table
            
            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue
                    
                clean_item = {}
                
                # Проходим по каждому ключу
                for semantic_key, value in raw_item.items():
                    # Находим соответствие в маппинге
                    target_key = self.ITEMS_KEY_MAPPING.get(semantic_key)
                    
                    if target_key:
                        # Конвертируем типы
                        if target_key == "row_number":
                            clean_item[target_key] = self.clean_int_str(value)
                        elif target_key == "quantity":
                            # Если количество содержит единицу измерения
                            qty, unit = self.extract_unit_from_quantity(str(value))
                            clean_item[target_key] = qty
                            if unit and "unit" not in clean_item:
                                clean_item["unit"] = unit
                        elif target_key in ["price_without_vat", "sum_without_vat"]:
                            clean_item[target_key] = self.clean_number_str(value)
                        else:
                            clean_item[target_key] = str(value).strip()
                
                # Добавляем, если есть минимально необходимые данные
                if "item_name" in clean_item or "sum_without_vat" in clean_item:
                    all_items.append(clean_item)
        
        return all_items

    def _calculate_totals(self, items: List[Dict[str, Any]], header_amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Считает итоги"""
        # Считаем по строкам
        calc_subtotal = sum(item.get("sum_without_vat", 0.0) for item in items)
        
        # Берем из шапки (приоритет)
        header_total_no_vat = self.clean_number_str(header_amounts.get("total_without_vat", 0))
        header_vat = self.clean_number_str(header_amounts.get("vat_amount", 0))
        header_total_with_vat = self.clean_number_str(header_amounts.get("total_with_vat", 0))
        
        return {
            "currency": header_amounts.get("currency", "UAH").replace("грн.", "UAH").strip(),
            "subtotal_without_vat": header_total_no_vat if header_total_no_vat > 0 else calc_subtotal,
            "vat_amount": header_vat,
            "total_with_vat": header_total_with_vat,
            "total_items_count": len(items)
        }

    def _extract_amounts_in_words(self, other_fields: Any, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Извлекает суммы прописью"""
        result = {
            "total_summary": "",
            "total_value": "",
            "vat_value": ""
        }
        
        # other_fields может быть dict или list
        if isinstance(other_fields, dict):
            result["total_summary"] = other_fields.get("total_items_text", "")
            result["total_value"] = other_fields.get("total_amount_text", "")
            result["vat_value"] = other_fields.get("vat_amount_text", "")
        
        # Если нет в other_fields, ищем в fields
        if not result["total_summary"]:
            for field in fields:
                if isinstance(field, dict) and "найменувань" in field.get("value", "").lower():
                    result["total_summary"] = field["value"]
                    break
        
        return result

    def _extract_signatures(self, other_fields: Any, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Извлекает информацию о подписях"""
        # Упрощенная версия - можно доработать
        return {}

