"""
Движок тестирования парсинга против эталонных примеров
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import datetime

from ..core.config import Config
from ..core.models import InvoiceData
from ..services.orchestrator import Orchestrator
from ..utils.json_compare import compare_json

logger = logging.getLogger(__name__)


class TestEngine:
    """Движок для тестирования парсинга против эталонных примеров"""

    def __init__(self, config: Config):
        """
        Инициализация движка тестирования

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.orchestrator = Orchestrator(config)

    def _normalize_text_for_comparison(self, text: str) -> str:
        """
        Нормализация текста для сравнения:
        - Игнорирует различия в типах кавычек
        - Игнорирует различия в пробелах между символами
        - Игнорирует различия в пунктуации в конце (точки, запятые)

        Args:
            text: Текст для нормализации

        Returns:
            Нормализованный текст
        """
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        # Убираем все типы кавычек (они не имеют значения)
        quote_variants = [
            '"', '"', '"',  # Двойные кавычки
            '«', '»',  # Французские кавычки
            '„', '‟',  # Немецкие кавычки
            ''', ''',  # Одинарные типографские
            '‚', '‛',  # Одинарные
            "'",  # ASCII одинарная
        ]

        result = text
        for quote in quote_variants:
            result = result.replace(quote, '')

        # Убираем пробелы между символами (оставляем только один пробел между словами)
        # Разбиваем по пробелам и склеиваем обратно
        words = result.split()
        result = ' '.join(words)

        # Убираем пунктуацию в конце (точки, запятые, которые не имеют смыслового значения)
        result = result.rstrip('.,;:')

        # Приводим к нижнему регистру для сравнения
        result = result.lower().strip()

        return result

    def _normalize_quotes(self, text: str) -> str:
        """
        Нормализация кавычек для сравнения (старый метод, оставлен для совместимости)
        Заменяет все типы кавычек на стандартные двойные кавычки

        Args:
            text: Текст для нормализации

        Returns:
            Текст с нормализованными кавычками
        """
        if not isinstance(text, str):
            return text

        # Все типы кавычек заменяем на стандартные двойные
        quote_variants = [
            '"',  # ASCII двойные кавычки
            '"',  # Левая типографская двойная кавычка
            '"',  # Правая типографская двойная кавычка
            '«',  # Французская левая кавычка
            '»',  # Французская правая кавычка
            '„',  # Немецкая нижняя кавычка
            '‟',  # Двойная верхняя перевернутая кавычка
            ''',  # Одинарная левая типографская
            ''',  # Одинарная правая типографская
            '‚',  # Одинарная нижняя
            '‛',  # Одинарная верхняя перевернутая
            "'",  # ASCII одинарная
        ]

        result = text
        for quote in quote_variants:
            result = result.replace(quote, '"')

        return result

    def _normalize_number(self, value: Any) -> str:
        """
        Нормализация чисел для сравнения
        Убирает пробелы, заменяет запятые на точки

        Args:
            value: Значение для нормализации

        Returns:
            Нормализованная строка
        """
        if not isinstance(value, (str, int, float)):
            return str(value)

        # Конвертируем в строку
        str_value = str(value).strip()

        # Убираем пробелы (разделители тысяч)
        str_value = str_value.replace(' ', '').replace('\u00a0', '')

        # Заменяем запятую на точку (десятичный разделитель)
        str_value = str_value.replace(',', '.')

        return str_value

    def run_tests(self) -> Dict[str, Any]:
        """
        Запуск всех тестов

        Returns:
            Результаты тестирования
        """
        logger.info("Starting test run")

        examples_dir = self.config.examples_dir
        if not examples_dir.exists():
            logger.error(f"Examples directory not found: {examples_dir}")
            return {
                "success": False,
                "error": f"Examples directory not found: {examples_dir}"
            }

        # Поиск тестовых документов
        test_documents = self._find_test_documents(examples_dir)

        if not test_documents:
            logger.warning("No test documents found")
            return {
                "success": True,
                "total": 0,
                "passed": 0,
                "failed": 0,
                "tests": []
            }

        logger.info(f"Found {len(test_documents)} test document(s)")

        # Запуск тестов
        results = []
        passed = 0
        failed = 0

        for doc_path, expected_path in test_documents:
            try:
                result = self._run_single_test(doc_path, expected_path)
                results.append(result)

                if result["passed"]:
                    passed += 1
                else:
                    failed += 1

            except Exception as e:
                logger.error(f"Test failed for {doc_path}: {e}", exc_info=True)
                results.append({
                    "document": str(doc_path),
                    "passed": False,
                    "error": str(e)
                })
                failed += 1

        # Формирование итогового отчета
        report = {
            "success": True,
            "total": len(test_documents),
            "passed": passed,
            "failed": failed,
            "pass_rate": (passed / len(test_documents) * 100) if test_documents else 0,
            "tests": results,
            "timestamp": datetime.now().isoformat()
        }

        logger.info(f"Test run completed: {passed}/{len(test_documents)} passed")

        return report

    def _find_test_documents(self, examples_dir: Path) -> List[Tuple[Path, Path]]:
        """
        Поиск тестовых документов и соответствующих эталонов

        Логика: для каждого документа в /invoices ищется эталон в /examples с именем {filename}.json

        Args:
            examples_dir: Директория с примерами

        Returns:
            Список кортежей (путь к документу, путь к эталону)
        """
        test_documents = []

        # Ищем документы в invoices_dir
        invoices_dir = self.config.invoices_dir

        if not invoices_dir.exists():
            logger.warning(f"Invoices directory not found: {invoices_dir}")
            return test_documents

        # Поиск всех PDF и изображений в invoices
        for pattern in ['*.pdf', '*.jpg', '*.jpeg', '*.png']:
            for doc_path in invoices_dir.glob(pattern):
                # Поиск соответствующего JSON эталона в examples_dir
                # Имя эталона формируется как {имя_документа}.json
                expected_filename = f"{doc_path.stem}.json"
                expected_path = examples_dir / expected_filename

                if expected_path.exists():
                    test_documents.append((doc_path, expected_path))
                    logger.info(f"Found test pair: {doc_path.name} <-> {expected_path.name}")
                else:
                    logger.debug(f"No expected JSON for: {doc_path.name} (looking for {expected_filename})")

        return test_documents

    def _run_single_test(self, doc_path: Path, expected_path: Path) -> Dict[str, Any]:
        """
        Запуск одного теста

        Args:
            doc_path: Путь к тестовому документу
            expected_path: Путь к эталонному JSON

        Returns:
            Результат теста
        """
        logger.info(f"Running test: {doc_path.name}")

        # Загрузка эталонных данных
        with open(expected_path, 'r', encoding='utf-8') as f:
            expected_data = json.load(f)

        # Обработка документа
        import asyncio
        result = asyncio.run(self.orchestrator.process_document(doc_path))

        if not result["success"]:
            return {
                "document": str(doc_path),
                "passed": False,
                "error": result.get("error", "Unknown error")
            }

        # Получение фактических данных
        actual_data = result["data"]

        # Конвертация в dict для сравнения
        if isinstance(actual_data, InvoiceData):
            actual_dict = actual_data.model_dump()
        else:
            actual_dict = actual_data

        # Нормализация структур для сравнения (приводим к общему виду)
        expected_normalized = self._normalize_structure(expected_data)
        actual_normalized = self._normalize_structure(actual_dict)

        # 1. Сравниваем HEADER (шапку документа)
        header_differences = self._compare_header(expected_normalized, actual_normalized)

        # 2. Compare ITEMS
        # Убеждаемся что items это список
        expected_items = expected_normalized.get('items', [])
        actual_items = actual_normalized.get('items', [])

        if not isinstance(expected_items, list):
            expected_items = []
        if not isinstance(actual_items, list):
            actual_items = []

        item_differences = self._compare_items(expected_items, actual_items)

        # Объединяем все различия
        all_differences = header_differences + item_differences

        # Формируем результат по всем данным (header + items)
        total_fields = 0
        # Header: document metadata fields
        total_fields += 10
        # Items: по 5 полей на каждую строку
        if len(expected_normalized.get('items', [])) > 0:
            total_fields += len(expected_normalized['items']) * 5

        accuracy = 1.0 - (len(all_differences) / total_fields) if total_fields > 0 else 1.0

        comparison = {
            "match": len(all_differences) == 0,
            "accuracy": max(0.0, min(1.0, accuracy)),
            "differences": all_differences
        }

        # Все различия - это реальные ошибки данных
        real_differences = all_differences

        # Формирование результата
        test_result = {
            "document": str(doc_path),
            "passed": len(real_differences) == 0,
            "accuracy": comparison.get("accuracy", 0),
            "differences": real_differences,
            "expected": expected_data,
            "actual": actual_dict
        }

        if test_result["passed"]:
            logger.info(f"✓ Test passed: {doc_path.name}")
        else:
            logger.warning(f"✗ Test failed: {doc_path.name}")
            logger.warning(f"Real data differences: {len(real_differences)}")

        return test_result

    def _get_semantic_key_mapping(self) -> Dict[str, List[str]]:
        """
        Возвращает маппинг семантически эквивалентных ключей для сравнения

        Returns:
            Словарь {основной_ключ: [варианты_ключей]}
        """
        return {
            # Product name
            'item_name': ['item_name', 'item_description', 'product_name', 'name', 'description'],
            'item_description': ['item_name', 'item_description', 'product_name', 'name', 'description'],
            # Line number
            'row_number': ['row_number', 'no', 'index', 'number', 'index_field', 'item_number'],
            'no': ['row_number', 'no', 'index', 'number', 'index_field', 'item_number'],
            'item_number': ['row_number', 'no', 'index', 'number', 'index_field', 'item_number'],
            # Код УКТ ЗЕД
            'ukt_zed_code': ['ukt_zed_code', 'ukt_zed', 'ukt_zed_code_field', 'code'],
            'ukt_zed': ['ukt_zed_code', 'ukt_zed', 'ukt_zed_code_field', 'code'],
            # Quantity
            'quantity': ['quantity', 'qty', 'quantity_field'],
            # Unit of measure
            'unit': ['unit', 'unit_field'],
            # Price without VAT
            'price_without_vat': ['price_without_vat', 'unit_price', 'price', 'unit_price_field', 'price_no_vat', 'unit_price_without_vat'],
            'price_no_vat': ['price_without_vat', 'unit_price', 'price', 'unit_price_field', 'price_no_vat', 'unit_price_without_vat'],
            'unit_price_without_vat': ['price_without_vat', 'unit_price', 'price', 'unit_price_field', 'price_no_vat', 'unit_price_without_vat'],
            # Amount without VAT
            'sum_without_vat': ['sum_without_vat', 'amount_without_vat', 'total', 'sum_without_vat_field', 'amount_without_vat_field', 'sum_no_vat', 'total_price_without_vat'],
            'amount_without_vat': ['sum_without_vat', 'amount_without_vat', 'total', 'sum_without_vat_field', 'amount_without_vat_field', 'sum_no_vat', 'total_price_without_vat'],
            'sum_no_vat': ['sum_without_vat', 'amount_without_vat', 'total', 'sum_without_vat_field', 'amount_without_vat_field', 'sum_no_vat', 'total_price_without_vat'],
            'total_price_without_vat': ['sum_without_vat', 'amount_without_vat', 'total', 'sum_without_vat_field', 'amount_without_vat_field', 'sum_no_vat', 'total_price_without_vat'],
        }

    def _find_semantic_value(self, item: Dict, semantic_keys: List[str]) -> Any:
        """
        Ищет значение по семантическим ключам (проверяет все варианты)

        Args:
            item: Item object
            semantic_keys: Список семантически эквивалентных ключей

        Returns:
            Значение или None
        """
        for key in semantic_keys:
            if key in item:
                return item[key]
        return None

    def _extract_quantity_number(self, value: Any) -> str:
        """
        Извлекает число из количества (убирает единицы измерения)

        Args:
            value: Значение количества (может быть строкой с числом и единицами измерения, числом, или строкой с числом)

        Returns:
            Нормализованное число как строка
        """
        if value is None:
            return ''
        value_str = str(value).strip()
        # Убираем единицы измерения (шт, кг, м и т.д.)
        # Ищем число в начале строки
        match = re.match(r'^(\d+[.,]?\d*)', value_str)
        if match:
            num = match.group(1).replace(',', '.')
            return num
        return value_str

    def _compare_items(self, expected_items: List[Dict], actual_items: List[Dict]) -> List[Dict]:
        """
        Line-by-line comparison of items with semantic key mapping

        Args:
            expected_items: Expected items
            actual_items: Actual items

        Returns:
            Список различий
        """
        differences = []
        key_mapping = self._get_semantic_key_mapping()

        # Проверяем, есть ли данные в обеих структурах, даже если количество строк разное
        # Сначала собираем все данные из обеих структур для семантического сравнения
        expected_data_set = set()
        actual_data_set = set()

        for exp in expected_items:
            # Собираем ключевые данные строки для идентификации
            key_values = []
            for key in ['item_name', 'item_description', 'product_name', 'ukt_zed_code', 'ukt_zed', 'no', 'row_number']:
                value = exp.get(key, '')
                if value:
                    normalized = self._normalize_text_for_comparison(value)
                    if normalized:
                        key_values.append(normalized)
            if key_values:
                expected_data_set.add('|'.join(sorted(key_values)))

        for act in actual_items:
            key_values = []
            for key in ['item_name', 'item_description', 'product_name', 'ukt_zed_code', 'ukt_zed', 'no', 'row_number']:
                value = act.get(key, '')
                if value:
                    normalized = self._normalize_text_for_comparison(value)
                    if normalized:
                        key_values.append(normalized)
            if key_values:
                actual_data_set.add('|'.join(sorted(key_values)))

        # Определяем максимальную длину для сравнения
        max_len = max(len(expected_items), len(actual_items))

        for i in range(max_len):
            if i >= len(expected_items):
                # Проверяем, есть ли данные этой строки в expected_data_set
                # Если данные фактически присутствуют в другом формате, не показываем ошибку
                act = actual_items[i]
                key_values = []
                for key in ['item_name', 'item_description', 'product_name', 'ukt_zed_code', 'ukt_zed', 'no', 'row_number']:
                    value = act.get(key, '')
                    if value:
                        normalized = self._normalize_text_for_comparison(value)
                        if normalized:
                            key_values.append(normalized)

                if key_values:
                    act_signature = '|'.join(sorted(key_values))
                    # Если эти данные есть в expected (в любой строке), пропускаем
                    if act_signature in expected_data_set:
                        continue

                # Только если данные действительно лишние
                differences.append({
                    "path": f"items[{i}]",
                    "type": "missing_in_expected",
                    "expected": None,
                    "actual": f"Лишняя строка {i+1}",
                    "field": "item",
                    "line": i + 1
                })
                continue

            if i >= len(actual_items):
                # Аналогично для отсутствующих строк
                exp = expected_items[i]
                key_values = []
                for key in ['item_name', 'item_description', 'product_name', 'ukt_zed_code', 'ukt_zed', 'no', 'row_number']:
                    value = exp.get(key, '')
                    if value:
                        normalized = self._normalize_text_for_comparison(value)
                        if normalized:
                            key_values.append(normalized)

                if key_values:
                    exp_signature = '|'.join(sorted(key_values))
                    if exp_signature in actual_data_set:
                        continue

                differences.append({
                    "path": f"items[{i}]",
                    "type": "missing_in_actual",
                    "expected": f"Отсутствует строка {i+1}",
                    "actual": None,
                    "field": "item",
                    "line": i + 1
                })
                continue

            exp = expected_items[i]
            act = actual_items[i]

            # Собираем все уникальные ключи из обоих объектов
            all_keys = set(exp.keys()) | set(act.keys())

            # Создаем множество уже обработанных семантических групп
            processed_semantic_groups = set()

            # Определяем, является ли значение числом
            def is_numeric(value):
                """Проверяет, является ли значение числом"""
                if isinstance(value, (int, float)):
                    return True
                if isinstance(value, str):
                    value_clean = value.strip().replace(' ', '').replace(',', '.')
                    try:
                        float(value_clean)
                        return True
                    except (ValueError, AttributeError):
                        return False
                return False

            # Для каждого ключа ищем семантически эквивалентные значения
            for key in all_keys:
                # Определяем семантическую группу для этого ключа
                semantic_keys = None
                semantic_group_id = None
                for main_key, variants in key_mapping.items():
                    if key in variants:
                        semantic_keys = variants
                        semantic_group_id = tuple(sorted(variants))  # Уникальный ID группы
                        break

                # Если это семантическая группа, которую мы уже обработали, пропускаем
                if semantic_group_id and semantic_group_id in processed_semantic_groups:
                    continue

                if semantic_keys:
                    # Помечаем группу как обработанную
                    if semantic_group_id:
                        processed_semantic_groups.add(semantic_group_id)

                    # Ищем значение в обоих объектах по всем вариантам ключей
                    exp_value = self._find_semantic_value(exp, semantic_keys)
                    act_value = self._find_semantic_value(act, semantic_keys)
                    # Используем первый ключ из группы как имя поля для отчета
                    field_name = semantic_keys[0]
                else:
                    # Если нет маппинга, используем прямой ключ
                    exp_value = exp.get(key, '')
                    act_value = act.get(key, '')
                    field_name = key

                # Специальная обработка для quantity - извлекаем только число
                if field_name in ['quantity', 'qty', 'quantity_field'] or 'quantity' in str(field_name).lower():
                    exp_value = self._extract_quantity_number(exp_value)
                    act_value = self._extract_quantity_number(act_value)

                # Нормализуем для сравнения
                # Если оба значения числовые, используем нормализацию чисел
                if is_numeric(exp_value) and is_numeric(act_value):
                    exp_str = self._normalize_number(exp_value)
                    act_str = self._normalize_number(act_value)
                else:
                    # Для текста используем полную нормализацию текста
                    exp_str = self._normalize_text_for_comparison(exp_value)
                    act_str = self._normalize_text_for_comparison(act_value)

                # Проверяем, являются ли значения пустыми после нормализации
                exp_empty = not exp_str or exp_str == ''
                act_empty = not act_str or act_str == ''

                # Если оба значения пустые, пропускаем
                if exp_empty and act_empty:
                    continue

                # Если значения различаются после нормализации
                if exp_str != act_str:
                    differences.append({
                        "path": f"items[{i}].{field_name}",
                        "type": "mismatch",
                        "expected": str(exp_value).strip() if exp_value is not None else '',
                        "actual": str(act_value).strip() if act_value is not None else '',
                        "field": field_name,
                        "line": i + 1
                    })

        return differences

    def _compare_header(self, expected_norm: Dict[str, Any], actual_norm: Dict[str, Any]) -> List[Dict]:
        """
        Сравнение данных шапки документа

        Args:
            expected_norm: Нормализованные ожидаемые данные
            actual_norm: Нормализованные фактические данные

        Returns:
            Список различий в шапке
        """
        differences = []

        # Извлекаем данные из header (они могут быть на разных уровнях)
        exp_doc_info = {}
        act_doc_info = {}
        exp_parties = {}
        act_parties = {}
        exp_signatures = {}
        act_signatures = {}

        # Пытаемся найти document_info (может быть на верхнем уровне или в header_data)
        if 'document_info' in expected_norm:
            exp_doc_info = expected_norm['document_info']
        elif 'header_data' in expected_norm and isinstance(expected_norm['header_data'], dict):
            exp_doc_info = expected_norm['header_data'].get('document_info', {})

        if 'document_info' in actual_norm:
            act_doc_info = actual_norm['document_info']
        elif 'header_data' in actual_norm and isinstance(actual_norm['header_data'], dict):
            act_doc_info = actual_norm['header_data'].get('document_info', {})

        # Пытаемся найти parties (может быть на верхнем уровне или в header_data)
        if 'parties' in expected_norm:
            exp_parties = expected_norm['parties']
        elif 'header_data' in expected_norm and isinstance(expected_norm['header_data'], dict):
            exp_parties = expected_norm['header_data'].get('parties', {})

        if 'parties' in actual_norm:
            act_parties = actual_norm['parties']
        elif 'header_data' in actual_norm and isinstance(actual_norm['header_data'], dict):
            act_parties = actual_norm['header_data'].get('parties', {})

        # Пытаемся найти signatures (может быть на верхнем уровне или в header_data)
        if 'signatures' in expected_norm:
            exp_signatures = expected_norm['signatures']
        elif 'header_data' in expected_norm and isinstance(expected_norm['header_data'], dict):
            exp_signatures = expected_norm['header_data'].get('signatures', {})

        if 'signatures' in actual_norm:
            act_signatures = actual_norm['signatures']
        elif 'header_data' in actual_norm and isinstance(actual_norm['header_data'], dict):
            act_signatures = actual_norm['header_data'].get('signatures', {})

        # 1. Document number
        exp_number = str(exp_doc_info.get('number', '')).strip()
        act_number = str(act_doc_info.get('number', '')).strip()
        if exp_number and act_number and exp_number != act_number:
            differences.append({
                "path": "header.document_info.number",
                "type": "mismatch",
                "expected": exp_number,
                "actual": act_number,
                "description": "Document number"
            })

        # 2. Document date
        exp_date = str(exp_doc_info.get('date_iso', exp_doc_info.get('date', ''))).strip()
        act_date = str(act_doc_info.get('date_iso', act_doc_info.get('date', ''))).strip()
        if exp_date and act_date and exp_date != act_date:
            differences.append({
                "path": "header.document_info.date",
                "type": "mismatch",
                "expected": exp_date,
                "actual": act_date,
                "description": "Document date"
            })

        # 3. Performer/Supplier (performer/supplier)
        # Может быть как performer, так и supplier
        exp_performer = exp_parties.get('performer', exp_parties.get('supplier', {}))
        act_performer = act_parties.get('performer', act_parties.get('supplier', {}))

        # 3.1. Название исполнителя (с нормализацией текста)
        exp_perf_name_orig = str(exp_performer.get('name', exp_performer.get('full_name', ''))).strip()
        act_perf_name_orig = str(act_performer.get('name', act_performer.get('full_name', ''))).strip()
        exp_perf_name = self._normalize_text_for_comparison(exp_perf_name_orig)
        act_perf_name = self._normalize_text_for_comparison(act_perf_name_orig)
        if exp_perf_name and act_perf_name and exp_perf_name != act_perf_name:
            differences.append({
                "path": "header.parties.performer.name",
                "type": "mismatch",
                "expected": exp_perf_name_orig,  # Оригинал для отображения
                "actual": act_perf_name_orig,
                "description": "Название исполнителя"
            })

        # 3.2. Performer tax ID comparison
        exp_perf_edrpou = str(exp_performer.get('edrpou', '')).strip()
        act_perf_edrpou = str(act_performer.get('edrpou', '')).strip()
        if exp_perf_edrpou and act_perf_edrpou and exp_perf_edrpou != act_perf_edrpou:
            differences.append({
                "path": "header.parties.performer.edrpou",
                "type": "mismatch",
                "expected": exp_perf_edrpou,
                "actual": act_perf_edrpou,
                "description": "Performer tax ID mismatch"
            })

        # 3.3. Банк исполнителя (может быть в bank_name или bank_account.bank_name, с нормализацией кавычек)
        exp_perf_bank_orig = str(exp_performer.get('bank_name', '')).strip()
        if not exp_perf_bank_orig and isinstance(exp_performer.get('bank_account'), dict):
            exp_perf_bank_orig = str(exp_performer['bank_account'].get('bank_name', '')).strip()

        act_perf_bank_orig = str(act_performer.get('bank_name', '')).strip()
        if not act_perf_bank_orig and isinstance(act_performer.get('bank_account'), dict):
            act_perf_bank_orig = str(act_performer['bank_account'].get('bank_name', '')).strip()

        exp_perf_bank = self._normalize_text_for_comparison(exp_perf_bank_orig)
        act_perf_bank = self._normalize_text_for_comparison(act_perf_bank_orig)

        if exp_perf_bank and act_perf_bank and exp_perf_bank != act_perf_bank:
            differences.append({
                "path": "header.parties.performer.bank_name",
                "type": "mismatch",
                "expected": exp_perf_bank_orig,  # Оригинал для отображения
                "actual": act_perf_bank_orig,
                "description": "Банк исполнителя"
            })

        # 4. Customer/Buyer (customer/buyer)
        # Может быть как customer, так и buyer
        exp_customer = exp_parties.get('customer', exp_parties.get('buyer', {}))
        act_customer = act_parties.get('customer', act_parties.get('buyer', {}))

        # Customer name field comparison
        exp_cust_name_orig = str(exp_customer.get('name', exp_customer.get('full_name', ''))).strip()
        act_cust_name_orig = str(act_customer.get('name', act_customer.get('full_name', ''))).strip()
        exp_cust_name = self._normalize_text_for_comparison(exp_cust_name_orig)
        act_cust_name = self._normalize_text_for_comparison(act_cust_name_orig)
        if exp_cust_name and act_cust_name and exp_cust_name != act_cust_name:
            differences.append({
                "path": "header.parties.customer.name",
                "type": "mismatch",
                "expected": exp_cust_name_orig,  # Оригинал для отображения
                "actual": act_cust_name_orig,
                "description": "Customer name mismatch"
            })

        # Tax ID comparison
        exp_cust_edrpou = str(exp_customer.get('edrpou', '')).strip()
        act_cust_edrpou = str(act_customer.get('edrpou', '')).strip()
        if exp_cust_edrpou and act_cust_edrpou and exp_cust_edrpou != act_cust_edrpou:
            differences.append({
                "path": "header.parties.customer.edrpou",
                "type": "mismatch",
                "expected": exp_cust_edrpou,
                "actual": act_cust_edrpou,
                "description": "Tax ID mismatch"
            })

        # Bank name comparison
        exp_cust_bank_orig = str(exp_customer.get('bank_name', '')).strip()
        if not exp_cust_bank_orig and isinstance(exp_customer.get('bank_account'), dict):
            exp_cust_bank_orig = str(exp_customer['bank_account'].get('bank_name', '')).strip()

        act_cust_bank_orig = str(act_customer.get('bank_name', '')).strip()
        if not act_cust_bank_orig and isinstance(act_customer.get('bank_account'), dict):
            act_cust_bank_orig = str(act_customer['bank_account'].get('bank_name', '')).strip()

        exp_cust_bank = self._normalize_text_for_comparison(exp_cust_bank_orig)
        act_cust_bank = self._normalize_text_for_comparison(act_cust_bank_orig)

        if exp_cust_bank and act_cust_bank and exp_cust_bank != act_cust_bank:
            differences.append({
                "path": "header.parties.customer.bank_name",
                "type": "mismatch",
                "expected": exp_cust_bank_orig,  # Оригинал для отображения
                "actual": act_cust_bank_orig,
                "description": "Bank name mismatch"
            })

        # 5. Compare raw_block text fields
        exp_raw = str(exp_performer.get('raw_block', '')).lower()
        act_raw = str(act_performer.get('raw_block', '')).lower()

        # Проверяем, есть ли номер документа в raw_block и совпадает ли он
        if exp_number and act_number:
            exp_has_num = exp_number in exp_raw
            act_has_num = act_number in act_raw

            # Если номер должен быть в тексте, но его нет или он неправильный
            if exp_has_num and not act_has_num:
                differences.append({
                    "path": "header.raw_block.document_number",
                    "type": "mismatch",
                    "expected": f"Document number {exp_number} in text",
                    "actual": f"Document number not found or incorrect in text",
                    "description": "Document number in text block"
                })

        # 6. Сравнение signatures (подписи) - ОТКЛЮЧЕНО
        # Нормализуем структуры к единому виду и сравниваем как обычные данные
        if False and exp_signatures and act_signatures:
            def normalize_structure(data):
                """Приводит структуру к единому виду для сравнения"""
                if isinstance(data, dict):
                    return [v for v in data.values() if isinstance(v, dict)]
                elif isinstance(data, list):
                    return [v for v in data if isinstance(v, dict)]
                return []

            exp_sigs = normalize_structure(exp_signatures)
            act_sigs = normalize_structure(act_signatures)

            # Универсальное сравнение списков структур
            max_len = max(len(exp_sigs), len(act_sigs))
            for i in range(max_len):
                if i >= len(exp_sigs):
                    # Лишняя структура в actual
                    act_sig = act_sigs[i]
                    if isinstance(act_sig, dict):
                        for key, val in act_sig.items():
                            if isinstance(val, str) and val:
                                differences.append({
                                    "path": f"header.signatures[{i}].{key}",
                                    "type": "mismatch",
                                    "expected": "",
                                    "actual": val,
                                    "description": ""
                                })
                elif i >= len(act_sigs):
                    # Отсутствующая структура в actual
                    exp_sig = exp_sigs[i]
                    if isinstance(exp_sig, dict):
                        for key, val in exp_sig.items():
                            if isinstance(val, str) and val:
                                differences.append({
                                    "path": f"header.signatures[{i}].{key}",
                                    "type": "mismatch",
                                    "expected": val,
                                    "actual": "",
                                    "description": ""
                                })
                else:
                    # Сравниваем структуры
                    exp_sig = exp_sigs[i]
                    act_sig = act_sigs[i]
                    if isinstance(exp_sig, dict) and isinstance(act_sig, dict):
                        all_keys = set(exp_sig.keys()) | set(act_sig.keys())
                        for key in all_keys:
                            exp_val = exp_sig.get(key)
                            act_val = act_sig.get(key)
                            if isinstance(exp_val, str) and isinstance(act_val, str):
                                exp_norm = self._normalize_text_for_comparison(exp_val)
                                act_norm = self._normalize_text_for_comparison(act_val)
                                if exp_norm != act_norm:
                                    differences.append({
                                        "path": f"header.signatures[{i}].{key}",
                                        "type": "mismatch",
                                        "expected": exp_val,
                                        "actual": act_val,
                                        "description": ""
                                    })
                            elif exp_val != act_val:
                                differences.append({
                                    "path": f"header.signatures[{i}].{key}",
                                    "type": "mismatch",
                                    "expected": str(exp_val) if exp_val is not None else "",
                                    "actual": str(act_val) if act_val is not None else "",
                                    "description": ""
                                })

        return differences

    def _extract_comparable_values(self, data: Any, prefix: str = "") -> Dict[str, Any]:
        """
        Извлечение всех значимых значений из структуры независимо от вложенности

        Рекурсивно обходит структуру и извлекает все "листовые" значения
        (строки, числа), игнорируя структуру и названия полей.

        Args:
            data: Исходные данные
            prefix: Префикс пути (для отладки)

        Returns:
            Словарь с плоской структурой {описание: значение}
        """
        values = {}

        if data is None:
            return values

        if isinstance(data, dict):
            for key, value in data.items():
                # Игнорируем служебные поля
                if key in ['raw_block', 'timestamp', 'model', 'source_file']:
                    continue
                new_prefix = f"{prefix}.{key}" if prefix else key
                values.update(self._extract_comparable_values(value, new_prefix))
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_prefix = f"{prefix}[{i}]"
                values.update(self._extract_comparable_values(item, new_prefix))
        else:
            # Листовое значение - сохраняем
            # Нормализуем значение
            if isinstance(data, str):
                data = data.strip()
                if data:  # Только непустые строки
                    values[prefix] = data
            elif isinstance(data, (int, float)):
                values[prefix] = data
            elif data is not None:
                values[prefix] = str(data)

        return values

    def _normalize_structure(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Полностью динамическая нормализация - копирует структуру и находит items

        Args:
            data: Исходные данные

        Returns:
            Нормализованные данные с items для сравнения
        """
        normalized = {}

        if not isinstance(data, dict):
            return normalized

        # Копируем все ключи динамически
        for key, value in data.items():
            normalized[key] = value

        # Динамически ищем items - список dict который НЕ является fields (label/value)
        items_found = None

        def is_items_list(lst):
            """Проверяет является ли список items (не fields)"""
            if not isinstance(lst, list) or len(lst) == 0:
                return False
            if not isinstance(lst[0], dict):
                return False
            # Если dict содержит только 2 ключа - вероятно это fields (label/value)
            # Items обычно имеют больше ключей
            first_keys_count = len(lst[0].keys())
            if first_keys_count <= 2:
                return False
            return True

        # Ищем список на верхнем уровне (прямой line_items или items)
        for key, value in data.items():
            if is_items_list(value):
                items_found = value
                break

        # Если не нашли, ищем внутри вложенных структур
        if not items_found:
            # Проверяем table_data.line_items (прямой объект, не список)
            if 'table_data' in data and isinstance(data['table_data'], dict):
                table_data = data['table_data']
                if 'line_items' in table_data and is_items_list(table_data['line_items']):
                    items_found = table_data['line_items']

            # Проверяем tables[0].line_items (список таблиц)
            if not items_found:
                for key, value in data.items():
                    if isinstance(value, list) and len(value) > 0:
                        first_elem = value[0]
                        if isinstance(first_elem, dict):
                            # Ищем список внутри этого dict - это должен быть line_items
                            for sub_key, sub_value in first_elem.items():
                                if isinstance(sub_value, list) and is_items_list(sub_value):
                                    items_found = sub_value
                                    break
                        if items_found:
                            break

            # Также проверяем другие возможные структуры (tables как объект)
            if not items_found:
                for key, value in data.items():
                    if isinstance(value, dict):
                        # Проверяем прямые вложенные структуры
                        if 'line_items' in value and is_items_list(value['line_items']):
                            items_found = value['line_items']
                            break
                        # Проверяем вложенные структуры на один уровень глубже
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, dict) and 'line_items' in sub_value:
                                if is_items_list(sub_value['line_items']):
                                    items_found = sub_value['line_items']
                                    break
                        if items_found:
                            break

        # Сохраняем найденные items (только список, не dict)
        if items_found is not None and isinstance(items_found, list):
            normalized['items'] = items_found
        else:
            # Если items не найден, оставляем пустой список
            normalized['items'] = []

        return normalized

    def _filter_real_differences(self, differences: List[Dict]) -> List[Dict]:
        """
        Фильтрация различий - оставляем только реальные ошибки в данных

        Args:
            differences: Список всех различий

        Returns:
            Список реальных ошибок данных
        """
        real_diffs = []

        # Список полей, которые можно игнорировать при сравнении
        IGNORE_PATHS_CONTAINING = [
            'raw_block',  # Сырые данные
            'timestamp',  # Служебная метка времени
            'model',      # Название модели
        ]

        for diff in differences:
            path = diff.get('path', '')
            diff_type = diff.get('type', '')

            # Проверяем, не содержит ли путь игнорируемые поля
            if any(ignore in path for ignore in IGNORE_PATHS_CONTAINING):
                continue

            # Все типы различий важны для данных
            real_diffs.append(diff)

        return real_diffs

    def _get_readable_description(self, path: str, diff_type: str = '') -> str:
        """
        Преобразование технического пути в читаемый формат

        Args:
            path: Путь типа "line_items[0].ukt_zed_code"
            diff_type: Тип различия

        Returns:
            Путь с номером строки: "ukt_zed_code (строка 1)"
        """
        import re

        # Извлекаем индекс строки если есть
        match = re.search(r'\[(\d+)\]', path)
        row_num = int(match.group(1)) + 1 if match else None

        # Берем последнюю часть пути (техническое название поля)
        field_name = path.split('.')[-1].replace('_', ' ')

        # Добавляем префикс для missing полей
        prefix = ""
        if diff_type == 'missing_in_actual':
            prefix = "[отсутствует] "
        elif diff_type == 'missing_in_expected':
            prefix = "[лишнее] "

        # Формируем описание
        if row_num:
            return f"{prefix}{field_name} в строке {row_num}"
        else:
            return f"{prefix}{field_name}"

    def _format_value_for_display(self, value: Any) -> str:
        """
        Форматирование значения для отображения

        Args:
            value: Значение

        Returns:
            Отформатированная строка
        """
        if value is None:
            return "отсутствует"
        if isinstance(value, (dict, list)):
            return f"{type(value).__name__}"

        value_str = str(value)
        # Ограничиваем длину
        if len(value_str) > 50:
            return value_str[:47] + "..."
        return value_str

    def generate_report(self, results: Dict[str, Any], output_path: Path):
        """
        Генерация отчета о тестировании

        Args:
            results: Результаты тестирования
            output_path: Путь для сохранения отчета
        """
        try:
            # Сохранение JSON отчета
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"Test report saved: {output_path}")

            # Вывод краткой статистики
            print("\n" + "=" * 60)
            print("TEST RESULTS")
            print("=" * 60)
            print(f"Total tests: {results['total']}")
            print(f"Passed: {results['passed']}")
            print(f"Failed: {results['failed']}")
            print(f"Pass rate: {results['pass_rate']:.2f}%")
            print("=" * 60 + "\n")

            # Детали по failed тестам
            if results['failed'] > 0:
                print("Failed tests details:\n")
                for test in results['tests']:
                    if not test['passed']:
                        doc_name = Path(test['document']).name
                        print(f"📄 {doc_name}")

                        if 'error' in test:
                            print(f"   ❌ Error: {test['error']}\n")
                        elif 'differences' in test:
                            diff_count = len(test['differences'])
                            print(f"   ⚠️  Total differences: {diff_count}\n")

                            # Выводим список реальных ошибок данных
                            if diff_count == 0:
                                print("   ✅ No data errors found\n")
                            else:
                                print("   Data errors:")
                                # Показываем только первые 20 ошибок
                                display_limit = 20
                                for i, diff in enumerate(test['differences'][:display_limit], 1):
                                    path = diff.get('path', 'unknown')
                                    diff_type = diff.get('type', '')
                                    expected = diff.get('expected', '')
                                    actual = diff.get('actual', '')
                                    line = diff.get('line', None)

                                    # Извлекаем читаемое описание из пути
                                    description = self._get_readable_description(path, diff_type)

                                    # Форматируем значения для вывода
                                    exp_str = self._format_value_for_display(expected)
                                    act_str = self._format_value_for_display(actual)

                                    # Добавляем номер строки если есть
                                    line_prefix = f"строка {line}: " if line else ""

                                    # Компактный вывод
                                    if diff_type == 'missing_in_actual':
                                        print(f"   {i}. {line_prefix}{description} - ожидалось '{exp_str}'")
                                    elif diff_type == 'missing_in_expected':
                                        print(f"   {i}. {line_prefix}{description} - получено '{act_str}'")
                                    else:
                                        print(f"   {i}. {line_prefix}{description}: {exp_str} vs {act_str}")

                            if diff_count > display_limit:
                                print(f"   ... и еще {diff_count - display_limit} ошибок")
                                print(f"   Полный отчет: {output_path}\n")
                print()

        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
