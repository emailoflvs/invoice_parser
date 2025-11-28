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

    # НЕТ статического маппинга - используем только column_mapping от Gemini!

    @staticmethod
    def clean_number_str(value: Any) -> float:
        """Converts string numbers to float"""
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
        """Converts string numbers to integers"""
        if isinstance(value, int):
            return value
        val_float = InvoicePostProcessor.clean_number_str(value)
        return int(val_float)

    @staticmethod
    def extract_unit_from_quantity(quantity_str: str) -> tuple[float, str]:
        """Extracts quantity and unit from quantity string"""
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

        # 2. Обработка Items (сохраняем как есть + column_mapping)
        tables = items_json.get("tables", [])
        final_invoice["line_items"] = self._normalize_line_items(tables)

        # Сохраняем column_mapping из первой таблицы (если есть)
        if tables and isinstance(tables[0], dict):
            final_invoice["_column_mapping"] = tables[0].get("column_mapping", {})

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
        """Возвращает document_info как есть"""
        return dict(doc_info)

    def _normalize_parties(self, raw_parties: Dict[str, Any]) -> Dict[str, Any]:
        """Возвращает parties как есть"""
        # Берем данные как есть, без маппинга ролей
        return dict(raw_parties)

    def _normalize_references(self, contract_ref: Dict[str, Any]) -> Dict[str, Any]:
        """Возвращает references как есть"""
        return dict(contract_ref)

    def _normalize_line_items(self, tables: List) -> List[Dict[str, Any]]:
        """
        Превращает таблицы Gemini в плоский список товаров.
        Использует column_mapping для преобразования СЫРЫХ заголовков в целевые ключи.
        """
        all_items = []

        for table in tables:
            # Извлекаем column_mapping и line_items
            column_mapping = {}
            raw_items = []

            if isinstance(table, dict):
                # Новый формат с column_mapping
                column_mapping = table.get("column_mapping", {})
                raw_items = table.get("line_items", [])
            elif isinstance(table, list):
                # Старый формат без column_mapping
                raw_items = table

            # Сохраняем column_mapping для финального JSON (если нужно)
            # Используем данные от Gemini напрямую без преобразований

            for raw_item in raw_items:
                if not isinstance(raw_item, dict):
                    continue

                # Просто копируем данные как есть
                clean_item = dict(raw_item)

                # Добавляем все items без фильтрации
                if clean_item:
                    all_items.append(clean_item)

        return all_items

    def _create_final_column_map(self, column_mapping: Dict[str, str]) -> Dict[str, str]:
        """
        Создает финальную карту: СЫРОЙ_ЗАГОЛОВОК -> ЦЕЛЕВОЙ_КЛЮЧ

        column_mapping из Gemini: {"abstract_role": "СЫРОЙ ЗАГОЛОВОК"}
        Возвращает: {"СЫРОЙ ЗАГОЛОВОК": "target_key"}
        """
        final_map = {}

        for abstract_role, raw_header in column_mapping.items():
            # Преобразуем абстрактную роль в целевой ключ
            target_key = self.ABSTRACT_TO_TARGET_MAP.get(abstract_role)

            if target_key:
                final_map[raw_header] = target_key
                logger.debug(f"Маппинг: '{raw_header}' -> '{target_key}' (через '{abstract_role}')")
            else:
                logger.warning(f"Неизвестная абстрактная роль: '{abstract_role}'")

        return final_map

    def _calculate_totals(self, items: List[Dict[str, Any]], header_amounts: Dict[str, Any]) -> Dict[str, Any]:
        """Возвращает totals как есть из header"""
        # Берем данные как есть, без вычислений и жестко заданных ключей
        return dict(header_amounts)

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

