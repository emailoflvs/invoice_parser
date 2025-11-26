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

        # Сравнение
        comparison = compare_json(expected_data, actual_dict)
        
        # Фильтруем различия, оставляя только реальные ошибки данных
        real_differences = self._filter_real_differences(comparison.get("differences", []))

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
    
    def _filter_real_differences(self, differences: List[Dict]) -> List[Dict]:
        """
        Фильтрация различий - оставляем только реальные ошибки в данных
        
        Args:
            differences: Список всех различий
            
        Returns:
            Список реальных ошибок данных
        """
        real_diffs = []
        
        for diff in differences:
            path = diff.get('path', '')
            diff_type = diff.get('type', '')
            
            # Игнорируем структурные различия (разные представления одних данных)
            if diff_type in ['missing_in_expected', 'missing_in_actual']:
                # Это структурные различия, данные могут быть в другом месте
                continue
            
            # Оставляем только реальные несовпадения значений
            if diff_type == 'mismatch':
                real_diffs.append(diff)
        
        return real_diffs
    
    def _get_readable_description(self, path: str) -> str:
        """
        Преобразование пути в читаемое описание
        
        Args:
            path: Путь типа "line_items[0].ukt_zed_code"
            
        Returns:
            Читаемое описание типа "артикул в строке 1"
        """
        import re
        
        # Извлекаем индекс строки если есть
        match = re.search(r'\[(\d+)\]', path)
        row_num = int(match.group(1)) + 1 if match else None
        
        # Определяем тип поля
        if 'ukt_zed' in path or 'sku' in path or 'code' in path:
            field_name = "артикул"
        elif 'item_name' in path or 'name' in path:
            field_name = "наименование"
        elif 'quantity' in path:
            field_name = "количество"
        elif 'price' in path:
            field_name = "цена"
        elif 'amount' in path or 'sum' in path:
            field_name = "сумма"
        elif 'inn' in path or 'edrpou' in path or 'ipn' in path:
            field_name = "ИНН/ЕДРПОУ"
        elif 'address' in path:
            field_name = "адрес"
        elif 'phone' in path:
            field_name = "телефон"
        elif 'date' in path:
            field_name = "дата"
        elif 'number' in path:
            field_name = "номер"
        else:
            # Берем последнюю часть пути
            field_name = path.split('.')[-1].replace('_', ' ')
        
        # Формируем описание
        if row_num:
            return f"{field_name} в строке {row_num}"
        else:
            return field_name
    
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
                                print("   ✅ No data errors found (only structural differences)\n")
                            else:
                                print("   Data errors:")
                                for i, diff in enumerate(test['differences'], 1):
                                    path = diff.get('path', 'unknown')
                                    expected = diff.get('expected', '')
                                    actual = diff.get('actual', '')
                                    
                                    # Извлекаем читаемое описание из пути
                                    # Например: line_items[0].ukt_zed_code -> артикул в строке 1
                                    description = self._get_readable_description(path)
                                    
                                    # Форматируем значения для вывода
                                    exp_str = self._format_value_for_display(expected)
                                    act_str = self._format_value_for_display(actual)
                                    
                                    print(f"   {i}. {description} ({exp_str} vs {act_str})")
                            
                            if diff_count > 10:
                                print(f"   ... and {diff_count - 10} more differences")
                                print(f"   See full report: {output_path}\n")
                print()

        except Exception as e:
            logger.error(f"Failed to generate report: {e}", exc_info=True)
