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

        # Сравниваем товары построчно (самое важное)
        item_differences = self._compare_items(
            expected_normalized.get('items', []),
            actual_normalized.get('items', [])
        )
        
        # Формируем результат только по товарам
        accuracy = 1.0
        if len(expected_normalized.get('items', [])) > 0:
            item_fields_count = len(expected_normalized['items']) * 5  # article, name, qty, price, amount
            accuracy = 1.0 - (len(item_differences) / item_fields_count) if item_fields_count > 0 else 1.0
        
        comparison = {
            "match": len(item_differences) == 0,
            "accuracy": max(0.0, min(1.0, accuracy)),
            "differences": item_differences
        }
        
        # Фильтруем различия, оставляя только реальные ошибки данных
        real_differences = item_differences  # Товары - это и есть реальные данные

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
            
            # Сравниваем критичные поля
            # 1. Артикул
            exp_article = str(exp.get('article', '')).strip()
            act_article = str(act.get('article', '')).strip()
            if exp_article != act_article:
                differences.append({
                    "path": f"items[{i}].article",
                    "type": "mismatch",
                    "expected": exp_article,
                    "actual": act_article,
                    "line": i + 1
                })
            
            # 2. Наименование
            exp_name = str(exp.get('product_name', '')).strip()
            act_name = str(act.get('product_name', '')).strip()
            if exp_name != act_name:
                differences.append({
                    "path": f"items[{i}].product_name",
                    "type": "mismatch",
                    "expected": exp_name,
                    "actual": act_name,
                    "line": i + 1
                })
            
            # 3. Количество (с точностью до 0.01)
            try:
                exp_qty = float(exp.get('quantity', 0))
                act_qty = float(act.get('quantity', 0))
                if abs(exp_qty - act_qty) > 0.01:
                    differences.append({
                        "path": f"items[{i}].quantity",
                        "type": "mismatch",
                        "expected": exp_qty,
                        "actual": act_qty,
                        "line": i + 1
                    })
            except (ValueError, TypeError):
                pass
            
            # 4. Цена (с точностью до 0.01)
            try:
                exp_price = float(exp.get('price_no_vat', 0))
                act_price = float(act.get('price_no_vat', 0))
                if abs(exp_price - act_price) > 0.01:
                    differences.append({
                        "path": f"items[{i}].price_no_vat",
                        "type": "mismatch",
                        "expected": exp_price,
                        "actual": act_price,
                        "line": i + 1
                    })
            except (ValueError, TypeError):
                pass
            
            # 5. Сумма (с точностью до 0.01)
            try:
                exp_sum = float(exp.get('sum_no_vat', 0))
                act_sum = float(act.get('sum_no_vat', 0))
                if abs(exp_sum - act_sum) > 0.01:
                    differences.append({
                        "path": f"items[{i}].sum_no_vat",
                        "type": "mismatch",
                        "expected": exp_sum,
                        "actual": act_sum,
                        "line": i + 1
                    })
            except (ValueError, TypeError):
                pass
        
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
        
        # Если есть вложенный header.header, разворачиваем его
        if 'header' in data and isinstance(data['header'], dict):
            header_data = data['header']
            if 'header' in header_data:
                # Двойной header - берем внутренний
                header_data = header_data['header']
            
            # Извлекаем данные из header
            for key, value in header_data.items():
                if key not in ['raw_block']:
                    normalized[key] = value
        
        # Обрабатываем tables -> items
        if 'tables' in data and isinstance(data['tables'], list) and len(data['tables']) > 0:
            # Берем первую таблицу
            table = data['tables'][0]
            
            # Таблица может быть списком строк или словарем с ключом rows
            rows = []
            if isinstance(table, list):
                rows = table
            elif isinstance(table, dict) and 'rows' in table:
                rows = table['rows']
            
            # Преобразуем rows в items
            items = []
            for row in rows:
                # Пропускаем итоговые строки (где нет номера или наименование начинается с "Разом", "Сума", "Всього")
                row_num = row.get('№', '')
                product_name = row.get('Продукція', row.get('Товар', row.get('product_name', row.get('name', ''))))
                
                # Проверяем, является ли строка итоговой
                if not row_num or str(row_num).strip() == '':
                    # Проверяем наименование
                    if isinstance(product_name, str):
                        product_name_lower = product_name.lower().strip()
                        if any(keyword in product_name_lower for keyword in ['разом', 'сума', 'всього', 'итого', 'пдв']):
                            continue  # Пропускаем итоговую строку
                
                item = {}
                # Маппинг полей - нужно поддерживать разные форматы
                # Формат 1: {'№': '1', 'Артикул': '...', 'Продукція': '...', ...}
                # Формат 2: {'№': '1', 'УКТ ЗЕД': '...', 'Товар': '...', ...}
                # Формат 3: {'line_number': 1, 'article': '...', 'product_name': '...', ...}
                
                # Номер строки / ID
                if '№' in row:
                    try:
                        item['id'] = int(row['№'])
                    except (ValueError, TypeError):
                        item['id'] = row['№']
                elif 'line_number' in row:
                    item['id'] = row['line_number']
                
                # Артикул (может быть в разных полях)
                if 'Артикул' in row:
                    item['article'] = str(row['Артикул']).strip()
                elif 'УКТ ЗЕД' in row:
                    item['article'] = str(row['УКТ ЗЕД']).strip()
                elif 'article' in row:
                    item['article'] = str(row['article']).strip()
                elif 'sku' in row:
                    item['article'] = str(row['sku']).strip()
                elif 'ukt_zed_code' in row:
                    item['article'] = str(row['ukt_zed_code']).strip()
                
                # Наименование
                if 'Продукція' in row:
                    item['product_name'] = str(row['Продукція']).strip()
                elif 'Товар' in row:
                    item['product_name'] = str(row['Товар']).strip()
                elif 'product_name' in row:
                    item['product_name'] = str(row['product_name']).strip()
                elif 'name' in row:
                    item['product_name'] = str(row['name']).strip()
                elif 'item_name' in row:
                    item['product_name'] = str(row['item_name']).strip()
                
                # Количество
                if 'Кількість' in row:
                    qty_str = str(row['Кількість']).replace('шт', '').replace(' ', '').replace(',', '.').strip()
                    try:
                        item['quantity'] = float(qty_str)
                    except:
                        item['quantity'] = 0
                elif 'quantity' in row:
                    item['quantity'] = row['quantity']
                
                # Единица измерения
                if 'Кількість' in row and 'шт' in str(row['Кількість']):
                    item['unit'] = 'шт'
                elif 'unit' in row:
                    item['unit'] = row['unit']
                
                # Цена
                if 'Ціна без ПДВ' in row:
                    price_str = str(row['Ціна без ПДВ']).replace(' ', '').replace(',', '.').strip()
                    try:
                        item['price_no_vat'] = float(price_str)
                    except:
                        item['price_no_vat'] = 0
                elif 'unit_price' in row:
                    item['price_no_vat'] = row['unit_price']
                elif 'price' in row:
                    item['price_no_vat'] = row['price']
                
                # Сумма
                if 'Сума без ПДВ' in row:
                    sum_str = str(row['Сума без ПДВ']).replace(' ', '').replace(',', '.').strip()
                    try:
                        item['sum_no_vat'] = float(sum_str)
                    except:
                        item['sum_no_vat'] = 0
                elif 'total_price' in row:
                    item['sum_no_vat'] = row['total_price']
                elif 'amount' in row:
                    item['sum_no_vat'] = row['amount']
                
                items.append(item)
            
            normalized['items'] = items
        
        # Если items уже есть напрямую, используем их
        if 'items' in data:
            normalized['items'] = data['items']
        elif 'line_items' in data:
            # Маппинг line_items -> items
            normalized['items'] = []
            for item in data['line_items']:
                mapped_item = {}
                # Маппинг полей из line_items
                if 'row_number' in item:
                    mapped_item['id'] = item['row_number']
                if 'ukt_zed_code' in item:
                    mapped_item['article'] = str(item['ukt_zed_code']).strip()
                if 'item_name' in item:
                    mapped_item['product_name'] = str(item['item_name']).strip()
                if 'quantity' in item:
                    mapped_item['quantity'] = item['quantity']
                if 'unit' in item:
                    mapped_item['unit'] = item['unit']
                if 'price_without_vat' in item:
                    mapped_item['price_no_vat'] = item['price_without_vat']
                if 'sum_without_vat' in item:
                    mapped_item['sum_no_vat'] = item['sum_without_vat']
                normalized['items'].append(mapped_item)
        
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
        Преобразование пути в читаемое описание
        
        Args:
            path: Путь типа "line_items[0].ukt_zed_code"
            diff_type: Тип различия
            
        Returns:
            Читаемое описание типа "артикул в строке 1"
        """
        import re
        
        # Извлекаем индекс строки если есть
        match = re.search(r'\[(\d+)\]', path)
        row_num = int(match.group(1)) + 1 if match else None
        
        # Определяем тип поля
        path_lower = path.lower()
        if 'article' in path_lower or 'ukt_zed' in path_lower or 'sku' in path_lower or 'code' in path_lower:
            field_name = "артикул"
        elif 'product_name' in path_lower or 'item_name' in path_lower or ('name' in path_lower and 'line_items' in path):
            field_name = "наименование"
        elif 'quantity' in path_lower:
            field_name = "количество"
        elif 'price' in path_lower and 'unit' in path_lower:
            field_name = "цена"
        elif 'amount' in path_lower or 'sum' in path_lower:
            field_name = "сумма"
        elif 'inn' in path_lower or 'edrpou' in path_lower or 'ipn' in path_lower or 'едрпоу' in path_lower:
            field_name = "ЕДРПОУ/ІПН"
        elif 'address' in path_lower or 'адрес' in path_lower:
            field_name = "адрес"
        elif 'phone' in path_lower:
            field_name = "телефон"
        elif 'date' in path_lower and 'document' not in path_lower:
            field_name = "дата"
        elif 'number' in path_lower and 'document' not in path_lower and 'line' not in path_lower:
            field_name = "номер"
        elif 'supplier' in path_lower or 'виконавець' in path_lower:
            field_name = "поставщик"
        elif 'customer' in path_lower or 'замовник' in path_lower:
            field_name = "заказчик"
        elif 'contract' in path_lower or 'договір' in path_lower:
            field_name = "договор"
        else:
            # Берем последнюю часть пути
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
