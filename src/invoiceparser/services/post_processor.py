"""
Post-процессор - объединяет данные от Gemini в целевую структуру
"""
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class InvoicePostProcessor:
    """
    Объединяет header и items данные в единую структуру
    """

    def process(self, header_json: Dict[str, Any], items_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        Объединяет header и items в целевую структуру

        Args:
            header_json: Результат парсинга header.txt
            items_json: Результат парсинга items.txt

        Returns:
            Объединенный dict со структурой:
            {
                ...header_fields,
                "table_data": {
                    "column_mapping": ...,
                    "line_items": ...
                }
            }
        """
        # 1. Базовая структура из header
        result = dict(header_json)

        # 2. Формируем table_data из items
        table_data = {}

        # Извлекаем основные ключи таблицы
        if "column_mapping" in items_json:
            table_data["column_mapping"] = items_json["column_mapping"]

        if "line_items" in items_json:
            table_data["line_items"] = items_json["line_items"]

        # Если items_json пустой или имеет другую структуру, сохраняем как есть в table_data
        if not table_data and items_json:
             # Если items_json это просто dict с другими ключами, сохраняем их
             table_data = items_json

        result["table_data"] = table_data

        # 3. Пост-обработка числовых полей в totals (safety net)
        if "totals" in result and isinstance(result["totals"], dict):
            self._normalize_totals(result["totals"])

        # 4. Пост-обработка line_items (safety net для quantity/price)
        if "line_items" in table_data and isinstance(table_data["line_items"], list):
            self._normalize_line_items(table_data["line_items"])

        return result

    def _normalize_totals(self, totals: Dict[str, Any]):
        """Преобразует строки в числа в totals"""
        numeric_keys = ["total", "vat", "total_with_vat", "subtotal"]
        for key in numeric_keys:
            if key in totals:
                val = totals[key]
                # Если это уже число, пропускаем
                if isinstance(val, (int, float)):
                    continue

                if isinstance(val, str):
                    try:
                        totals[key] = self._parse_number(val)
                    except ValueError:
                        logger.warning(f"Could not convert total '{key}'='{val}' to number")

    def _normalize_line_items(self, items: list):
        """Пытается преобразовать числовые поля в строках таблицы"""
        numeric_keys = ["quantity", "price", "amount", "price_excluding_vat", "amount_excluding_vat", "price_with_vat"]

        for item in items:
            if not isinstance(item, dict):
                continue

            for key, val in item.items():
                # Проверяем, похоже ли название ключа на числовое поле
                is_numeric = any(nk in key for nk in numeric_keys)

                if is_numeric and isinstance(val, str):
                    try:
                        # Пытаемся сконвертировать, но аккуратно
                        # Если в строке есть буквы (кроме e/E для экспоненты), пропускаем
                        import re
                        if re.search(r'[a-zA-Zа-яА-Я]', val):
                            continue

                        item[key] = self._parse_number(val)
                    except ValueError:
                        pass # Не страшно, оставляем как строку

    def _parse_number(self, val: str) -> float:
        """Парсит строку в число, обрабатывая разделители"""
        # Удаляем пробелы и неразрывные пробелы
        clean_val = val.replace(" ", "").replace("\u00a0", "")

        # Если пустая строка
        if not clean_val:
            return 0.0

        # Обработка запятых и точек
        if "," in clean_val and "." not in clean_val:
            # "1234,56" -> 1234.56
            clean_val = clean_val.replace(",", ".")
        elif "," in clean_val and "." in clean_val:
            # "1,234.56" -> 1234.56 (en)
            if clean_val.find(",") < clean_val.find("."):
                clean_val = clean_val.replace(",", "")
            else:
                # "1.234,56" -> 1234.56 (eu)
                clean_val = clean_val.replace(".", "").replace(",", ".")

        return float(clean_val)
