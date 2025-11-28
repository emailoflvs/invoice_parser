"""
Движок тестирования парсинга против эталонных примеров
"""
import json
import logging
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

    def _normalize_quotes(self, text: str) -> str:
        """
        Нормализация кавычек для сравнения
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
                # Например: invoice.jpg -> examples/invoice.json
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
        result = self.orchestrator.process_document(doc_path)

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

        # 2. Сравниваем ITEMS (товары)
        item_differences = self._compare_items(
            expected_normalized.get('items', []),
            actual_normalized.get('items', [])
        )

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

    def _compare_items(self, expected_items: List[Dict], actual_items: List[Dict]) -> List[Dict]:
        """
        Построчное сравнение товаров

        Args:
            expected_items: Ожидаемые товары
            actual_items: Фактические товары

        Returns:
            Список различий
        """
        differences = []

        max_len = max(len(expected_items), len(actual_items))

        for i in range(max_len):
            if i >= len(expected_items):
                differences.append({
                    "path": f"items[{i}]",
                    "type": "missing_in_expected",
                    "expected": None,
                    "actual": f"Лишняя строка {i+1}"
                })
                continue

            if i >= len(actual_items):
                differences.append({
                    "path": f"items[{i}]",
                    "type": "missing_in_actual",
                    "expected": f"Отсутствует строка {i+1}",
                    "actual": None
                })
                continue

            exp = expected_items[i]
            act = actual_items[i]

            # Универсальное сравнение всех полей
            # Объединяем ключи из обоих объектов
            all_keys = set(exp.keys()) | set(act.keys())

            for key in all_keys:
                exp_value = exp.get(key, '')
                act_value = act.get(key, '')

                # Нормализуем для сравнения
                exp_str = self._normalize_quotes(str(exp_value).strip())
                act_str = self._normalize_quotes(str(act_value).strip())

                if exp_str != act_str:
                    differences.append({
                        "path": f"items[{i}].{key}",
                        "type": "mismatch",
                        "expected": str(exp_value).strip(),
                        "actual": str(act_value).strip(),
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

        # Пытаемся найти document_info
        if 'document_info' in expected_norm:
            exp_doc_info = expected_norm['document_info']
        if 'document_info' in actual_norm:
            act_doc_info = actual_norm['document_info']

        # Пытаемся найти parties
        if 'parties' in expected_norm:
            exp_parties = expected_norm['parties']
        if 'parties' in actual_norm:
            act_parties = actual_norm['parties']

        # 1. Номер документа
        exp_number = str(exp_doc_info.get('number', '')).strip()
        act_number = str(act_doc_info.get('number', '')).strip()
        if exp_number and act_number and exp_number != act_number:
            differences.append({
                "path": "header.document_info.number",
                "type": "mismatch",
                "expected": exp_number,
                "actual": act_number,
                "description": "Номер документа"
            })

        # 2. Дата документа
        exp_date = str(exp_doc_info.get('date_iso', exp_doc_info.get('date', ''))).strip()
        act_date = str(act_doc_info.get('date_iso', act_doc_info.get('date', ''))).strip()
        if exp_date and act_date and exp_date != act_date:
            differences.append({
                "path": "header.document_info.date",
                "type": "mismatch",
                "expected": exp_date,
                "actual": act_date,
                "description": "Дата документа"
            })

        # 3. Исполнитель (performer)
        exp_performer = exp_parties.get('performer', {})
        act_performer = act_parties.get('performer', {})

        # 3.1. Название исполнителя (с нормализацией кавычек)
        exp_perf_name_orig = str(exp_performer.get('name', exp_performer.get('full_name', ''))).strip()
        act_perf_name_orig = str(act_performer.get('name', act_performer.get('full_name', ''))).strip()
        exp_perf_name = self._normalize_quotes(exp_perf_name_orig)
        act_perf_name = self._normalize_quotes(act_perf_name_orig)
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

        exp_perf_bank = self._normalize_quotes(exp_perf_bank_orig)
        act_perf_bank = self._normalize_quotes(act_perf_bank_orig)

        if exp_perf_bank and act_perf_bank and exp_perf_bank != act_perf_bank:
            differences.append({
                "path": "header.parties.performer.bank_name",
                "type": "mismatch",
                "expected": exp_perf_bank_orig,  # Оригинал для отображения
                "actual": act_perf_bank_orig,
                "description": "Банк исполнителя"
            })

        # 4. Заказчик (customer)
        exp_customer = exp_parties.get('customer', {})
        act_customer = act_parties.get('customer', {})

        # Customer name field comparison
        exp_cust_name_orig = str(exp_customer.get('name', exp_customer.get('full_name', ''))).strip()
        act_cust_name_orig = str(act_customer.get('name', act_customer.get('full_name', ''))).strip()
        exp_cust_name = self._normalize_quotes(exp_cust_name_orig)
        act_cust_name = self._normalize_quotes(act_cust_name_orig)
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

        exp_cust_bank = self._normalize_quotes(exp_cust_bank_orig)
        act_cust_bank = self._normalize_quotes(act_cust_bank_orig)

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
                    "expected": f"Номер {exp_number} в тексте",
                    "actual": f"Номер не найден или неверный в тексте",
                    "description": "Номер документа в текстовом блоке"
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
        Нормализация структуры данных для сравнения

        Приводит разные форматы вывода к единому виду для корректного сравнения

        Args:
            data: Исходные данные

        Returns:
            Нормализованные данные
        """
        normalized = {}

        # Извлекаем document_info и parties
        # Формат 1: данные на корневом уровне (эталонный JSON)
        if 'document_info' in data and 'parties' in data:
            normalized['document_info'] = data.get('document_info', {})
            normalized['parties'] = data.get('parties', {})
            normalized['contract_reference'] = data.get('contract_reference', {})
        # Формат 2: данные внутри header (actual JSON)
        elif 'header' in data and isinstance(data['header'], dict):
            header_data = data['header']
            if 'header' in header_data:
                # Двойной header - берем внутренний
                header_data = header_data['header']

            # Извлекаем данные из header и нормализуем названия полей
            normalized['document_info'] = header_data.get('document_info', {})

            # Нормализуем parties: full_name -> name
            parties = header_data.get('parties', {})
            if isinstance(parties, dict):
                normalized_parties = {}
                for role, party_data in parties.items():
                    if isinstance(party_data, dict):
                        normalized_party = party_data.copy()
                        # Маппинг: full_name -> name
                        if 'full_name' in normalized_party and 'name' not in normalized_party:
                            normalized_party['name'] = normalized_party['full_name']
                        normalized_parties[role] = normalized_party
                    else:
                        normalized_parties[role] = party_data
                normalized['parties'] = normalized_parties
            else:
                normalized['parties'] = parties

            normalized['contract_reference'] = header_data.get('contract_reference', {})

        # Обрабатываем items
        # Формат 1: items уже есть на корневом уровне (эталонный JSON)
        if 'items' in data and isinstance(data['items'], list):
            # Просто копируем items, они уже в правильном формате
            normalized['items'] = data['items']
            return normalized

        # Формат 2: tables -> items (actual JSON от Gemini)
        if 'tables' in data and isinstance(data['tables'], list) and len(data['tables']) > 0:
            # Берем первую таблицу
            table = data['tables'][0]

            # Таблица может быть списком строк или словарем с ключом rows
            rows = []
            if isinstance(table, list):
                rows = table
            elif isinstance(table, dict) and 'rows' in table:
                rows = table['rows']

            # Просто берем rows как есть - без преобразований
            normalized['items'] = rows

        # Если items уже есть напрямую, используем их
        if 'items' in data:
            normalized['items'] = data['items']
        elif 'line_items' in data:
            # Маппинг line_items -> items
            # Берем items как есть, без маппинга
            normalized['items'] = data['line_items']

        # Копируем остальные поля верхнего уровня
        for key in ['document_info', 'parties', 'contract_reference', 'totals', 'signatures', 'references', 'annotations']:
            if key in data:
                normalized[key] = data[key]

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
