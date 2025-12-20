"""
Post-процессор - объединяет данные от Gemini в целевую структуру
"""
import re
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
        # 1. Базовая структура из header - копируем ВСЕ поля без исключений
        result = dict(header_json)

        # Логируем ключи для отладки
        logger.debug(f"Header JSON keys: {list(header_json.keys())}")
        logger.debug(f"Result keys after copy: {list(result.keys())}")

        # 2. Формируем table_data из items
        table_data = {}

        # Извлекаем основные ключи таблицы
        if "column_mapping" in items_json:
            table_data["column_mapping"] = items_json["column_mapping"]

            # CRITICAL: Preserve column order from Gemini response
            # Priority 1: Use explicit column_order array from Gemini (preferred)
            # Priority 2: Fallback to Object.keys() order (modern JS preserves insertion order)
            if "column_order" in items_json and isinstance(items_json["column_order"], list) and len(items_json["column_order"]) > 0:
                # Use explicit order from Gemini, but filter out service fields
                raw_order = items_json["column_order"]
                # Filter out "raw" and other service fields
                table_data["column_order"] = [k for k in raw_order if k not in ['raw', '_meta', '_label'] and not k.startswith('_')]
                logger.info(f"✓ Using column_order from Gemini (filtered): {table_data['column_order']}")
                if len(raw_order) != len(table_data["column_order"]):
                    logger.info(f"  Filtered out service fields: {[k for k in raw_order if k not in table_data['column_order']]}")
            else:
                # Fallback: extract order from column_mapping keys, filter service fields
                raw_keys = list(items_json["column_mapping"].keys())
                table_data["column_order"] = [k for k in raw_keys if k not in ['raw', '_meta', '_label'] and not k.startswith('_')]
                logger.warning(f"⚠ column_order not found in Gemini response, using Object.keys(column_mapping) (filtered): {table_data['column_order']}")
                logger.warning("⚠ This may not preserve the original document column order! Update prompts to include column_order.")

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

        # 4. НЕ нормализуем line_items - оставляем строками для точного отображения
        # Конвертация в числа может привести к потере десятичных знаков (4341.66 → 4341.6)
        # Фронтенд сам обработает отображение чисел
        # if "line_items" in table_data and isinstance(table_data["line_items"], list):
        #     self._normalize_line_items(table_data["line_items"])

        return result

    def _normalize_totals(self, totals: Dict[str, Any]):
        """Преобразует строки в числа в totals"""
        # Обрабатываем все ключи динамически, проверяя содержимое
        for key, val in totals.items():
            # Если это уже число, пропускаем
            if isinstance(val, (int, float)):
                continue

            if isinstance(val, str):
                # Проверяем, является ли строка числом по содержимому
                if self._is_numeric_string(val):
                    try:
                        totals[key] = self._parse_number(val)
                    except ValueError:
                        logger.warning(f"Could not convert total '{key}'='{val}' to number")

    def _normalize_line_items(self, items: list):
        """Пытается преобразовать числовые поля в строках таблицы"""
        # Обрабатываем все поля динамически, проверяя содержимое
        for item in items:
            if not isinstance(item, dict):
                continue

            for key, val in item.items():
                if isinstance(val, str):
                    # Проверяем, является ли строка числом по содержимому
                    if self._is_numeric_string(val):
                        try:
                            item[key] = self._parse_number(val)
                        except ValueError:
                            pass  # Не страшно, оставляем как строку

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

    def _is_numeric_string(self, val: str) -> bool:
        """Проверяет, является ли строка числом по содержимому"""
        if not val or not isinstance(val, str):
            return False

        # Убираем пробелы и неразрывные пробелы
        clean_val = val.replace(" ", "").replace("\u00a0", "")

        if not clean_val:
            return False

        # Если в строке есть буквы (кроме e/E для экспоненты), это не число
        if re.search(r'[a-df-zA-DF-Z]', clean_val):  # Исключаем только e/E
            return False

        # Проверяем, что остались только цифры, запятые, точки, e/E и знаки +/-
        if re.match(r'^[+-]?[\d.,eE]+$', clean_val):
            return True

        return False
