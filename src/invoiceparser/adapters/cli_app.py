"""
CLI адаптер для работы с приложением через командную строку
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from ..core.config import Config
from ..services.orchestrator import Orchestrator
from ..services.test_engine import TestEngine

logger = logging.getLogger(__name__)


class CLIApp:
    """CLI приложение для парсинга документов"""

    def __init__(self, config: Config):
        """
        Инициализация CLI приложения

        Args:
            config: Конфигурация приложения
        """
        self.config = config
        self.orchestrator = Orchestrator(config)
        self.test_engine = TestEngine(config)

    def run(self, args: Optional[list] = None):
        """
        Запуск CLI приложения

        Args:
            args: Аргументы командной строки (если None, берутся из sys.argv)
        """
        parser = self._create_parser()
        parsed_args = parser.parse_args(args)

        # Обработка команды
        if parsed_args.command == 'parse':
            self._handle_parse(parsed_args)
        elif parsed_args.command == 'test':
            self._handle_test(parsed_args)
        elif parsed_args.command == 'info':
            self._handle_info(parsed_args)
        elif parsed_args.command == 'approve':
            self._handle_approve(parsed_args)
        else:
            parser.print_help()

    def _create_parser(self) -> argparse.ArgumentParser:
        """
        Создание парсера аргументов

        Returns:
            Парсер аргументов
        """
        parser = argparse.ArgumentParser(
            description='InvoiceParser - AI-powered document parser',
            formatter_class=argparse.RawDescriptionHelpFormatter
        )

        subparsers = parser.add_subparsers(dest='command', help='Available commands')

        # Команда parse
        parse_parser = subparsers.add_parser('parse', help='Parse a document')
        parse_parser.add_argument(
            '--path',
            type=str,
            required=True,
            help='Path to document (PDF or image)'
        )
        parse_parser.add_argument(
            '--output',
            type=str,
            help='Output directory (default: from config)'
        )
        parse_parser.add_argument(
            '--compare-with',
            type=str,
            help='Path to reference JSON file for comparison (test mode)'
        )

        # Команда test
        test_parser = subparsers.add_parser('test', help='Run tests against examples')
        test_parser.add_argument(
            '--output',
            type=str,
            help='Path to save test report'
        )

        # Команда info
        info_parser = subparsers.add_parser('info', help='Show configuration info')

        # Команда approve
        approve_parser = subparsers.add_parser('approve', help='Approve parsed data and export to configured formats')
        approve_parser.add_argument(
            '--json',
            type=str,
            required=True,
            help='Path to JSON file with parsed data'
        )
        approve_parser.add_argument(
            '--original-filename',
            type=str,
            help='Original filename (for export naming)'
        )

        return parser

    def _handle_parse(self, args):
        """
        Обработка команды parse

        Args:
            args: Аргументы команды
        """
        document_path = Path(args.path)

        if not document_path.exists():
            print(f"✗ Error: Document not found: {document_path}")
            sys.exit(1)

        compare_with = None
        if args.compare_with:
            compare_with = Path(args.compare_with)
            if not compare_with.exists():
                print(f"✗ Error: Reference file not found: {compare_with}")
                sys.exit(1)
            if self.config.mode.upper() != 'TEST':
                print(f"⚠️  Warning: --compare-with specified, but MODE != TEST. Testing will be skipped.")
                print(f"   Set MODE=TEST in .env to enable testing.\n")
                compare_with = None  # Игнорируем параметр, если не TEST режим

        print(f"\n{'=' * 60}")
        print(f"Parsing document: {document_path}")
        print(f"Model: {self.config.gemini_model}")
        if compare_with:
            print(f"Reference file for comparison: {compare_with}")
        if self.config.mode.upper() == 'TEST':
            print(f"Mode: TEST - comparison will be performed")
        print(f"{'=' * 60}\n")

        try:
            # Обработка документа
            import asyncio
            result = asyncio.run(self.orchestrator.process_document(document_path, compare_with=compare_with, source=None))

            # Вывод результата
            if result["success"]:
                elapsed_time = result.get('elapsed_time', 0)

                # Проверяем наличие результатов тестирования и выводим сразу
                test_results = result.get('test_results')
                if test_results and test_results.get('status') == 'tested':
                    error_count = test_results.get('errors', 0)
                    print(f"✓ Document parsed successfully (took {elapsed_time:.2f}s)")
                    print(f"\n{'=' * 60}")
                    if error_count == 0:
                        print(f"✅ TEST PASSED: 0 errors")
                    else:
                        print(f"❌ TEST FAILED: {error_count} errors found")
                    print(f"{'=' * 60}\n")
                else:
                    print(f"✓ Document parsed successfully (took {elapsed_time:.2f}s)\n")

                # Новая структура: данные на верхнем уровне
                data = result['data']

                # Просто показываем что данные получены, без жестко заданных полей
                items_count = 0
                if isinstance(data, dict) and 'line_items' in data:
                    items_count = len(data['line_items'])

                print(f"✓ Parsed successfully")
                print(f"Items found: {items_count}")

                # Вывод результатов теста если есть
                if test_results:
                    print(f"\n{'=' * 60}")
                    print("TEST RESULTS")
                    print(f"{'=' * 60}")
                    if test_results.get('status') == 'tested':
                        error_count = test_results.get('errors', 0)
                        reference_file = test_results.get('reference_file_name', 'unknown')
                        total_items = test_results.get('total_items', 0)

                        print(f"Reference file: {reference_file}")
                        print(f"Total items in reference: {total_items}")
                        print()

                        if error_count == 0:
                            print(f"✅ All data matched - 0 errors")
                        else:
                            print(f"❌ Found {error_count} errors:\n")
                            all_errors = test_results.get('all_errors', test_results.get('sample_errors', []))
                            for idx, error in enumerate(all_errors, 1):
                                print(f"  {idx}. {error}")

                            if error_count > len(all_errors):
                                print(f"\n  ... and {error_count - len(all_errors)} more errors (see JSON file for details)")
                    elif test_results.get('status') == 'no_reference':
                        print(f"ℹ️  No reference file found - skipped testing")
                        print(f"   Expected: {test_results.get('message', 'Unknown')}")
                    else:
                        print(f"⚠️  Test error: {test_results.get('message', 'Unknown')}")
                    print(f"{'=' * 60}")

                # Показываем имя сохраненного файла
                output_file = result.get('output_file')
                if output_file:
                    import os
                    print(f"\nResults saved to: {os.path.basename(output_file)}")
                else:
                    print(f"\nResults saved to: {self.config.output_dir}")
                print(f"Total processing time: {elapsed_time:.2f}s")
            else:
                print(f"✗ Failed to parse document")
                print(f"Error: {result['error']}")
                sys.exit(1)

        except Exception as e:
            print(f"\n✗ Error: {e}")
            logger.error(f"Parse command failed: {e}", exc_info=True)
            sys.exit(1)

        print(f"\n{'=' * 60}\n")

    def _handle_test(self, args):
        """
        Обработка команды test

        Args:
            args: Аргументы команды
        """
        print(f"\n{'=' * 60}")
        print("Running tests against examples")
        print(f"{'=' * 60}\n")

        try:
            # Запуск тестов
            results = self.test_engine.run_tests()

            # Проверка наличия тестов
            if results.get('total', 0) == 0:
                print("⚠ No test documents found in examples directory")
                print(f"Expected directory: {self.config.examples_dir}")
                print("\nTo use test mode:")
                print("1. Place test documents (PDF/images) in examples directory")
                print("2. Create corresponding .json files with expected results")
                sys.exit(0)

            # Генерация отчета
            if args.output:
                report_path = Path(args.output)
            else:
                from datetime import datetime
                timestamp = datetime.now().strftime("%d%m%H%M")
                failed_count = results.get('failed', 0)
                # Формат имени файла: {имя}_{timestamp}_{количество_ошибок}errors.json
                test_name = "test" if results.get('total', 0) > 1 else Path(results['tests'][0]['document']).stem
                report_path = self.config.output_dir / f"{test_name}_{timestamp}_{failed_count}errors.json"

            self.test_engine.generate_report(results, report_path)

            # Вывод результата
            if results['failed'] == 0:
                print("✓ All tests passed!")
                sys.exit(0)
            else:
                print(f"✗ Some tests failed")
                sys.exit(1)

        except Exception as e:
            print(f"\n✗ Error: {e}")
            logger.error(f"Test command failed: {e}", exc_info=True)
            sys.exit(1)

    def _handle_info(self, args):
        """
        Обработка команды info

        Args:
            args: Аргументы команды
        """
        print(f"\n{'=' * 60}")
        print("InvoiceParser Configuration")
        print(f"{'=' * 60}\n")

        print(f"Mode: {self.config.mode}")
        print(f"Log Level: {self.config.log_level}")
        print(f"\nDirectories:")
        print(f"  Invoices: {self.config.invoices_dir}")
        print(f"  Output: {self.config.output_dir}")
        print(f"  Logs: {self.config.logs_dir}")
        print(f"  Temp: {self.config.temp_dir}")

        print(f"\nGemini API:")
        print(f"  Model: {self.config.gemini_model}")
        print(f"  API Key: {'*' * 20}{self.config.gemini_api_key[-4:]}")

        print(f"\nImage Enhancement: {self.config.enable_image_enhancement}")
        if self.config.enable_image_enhancement:
            print(f"  Upscale Factor: {self.config.image_upscale_factor}")
            print(f"  Brightness: {self.config.image_brightness_factor}")
            print(f"  Contrast: {self.config.image_contrast_factor}")
            print(f"  Sharpness: {self.config.image_sharpness_factor}")

        print(f"\nPDF Processing:")
        print(f"  Mode: {self.config.pdf_processing_mode}")
        print(f"  DPI: {self.config.pdf_image_dpi}")
        print(f"  Max Pages: {self.config.pdf_max_pages}")

        print(f"\nExport:")
        print(f"  Excel (локальный): {self.config.export_local_excel_enabled}")
        print(f"  Excel (онлайн, Google Sheets): {self.config.export_online_excel_enabled}")
        print(f"  CRM: {self.config.export_crm_enabled}")

        print(f"\n{'=' * 60}\n")

    def _handle_approve(self, args):
        """
        Обработка команды approve - подтверждение данных и экспорт

        Args:
            args: Аргументы команды
        """
        import json
        import asyncio
        from pathlib import Path

        json_path = Path(args.json)

        if not json_path.exists():
            print(f"✗ Error: JSON file not found: {json_path}")
            sys.exit(1)

        print(f"\n{'=' * 60}")
        print(f"Approving data from: {json_path}")
        print(f"{'=' * 60}\n")

        try:
            # Загружаем данные из JSON
            with open(json_path, 'r', encoding='utf-8') as f:
                approved_data = json.load(f)

            # Получаем оригинальное имя файла
            original_filename = args.original_filename
            if not original_filename:
                # Пытаемся извлечь из данных или использовать имя JSON файла
                original_filename = approved_data.get('_meta', {}).get('source_file', json_path.stem)
                if isinstance(original_filename, str) and '/' in original_filename:
                    original_filename = Path(original_filename).name

            print(f"Original filename: {original_filename}")
            print(f"Exporting to configured formats...\n")

            # Инициализируем сервис экспорта
            from ..services.approved_data_export_service import ApprovedDataExportService
            export_service = ApprovedDataExportService(self.config)

            # Экспортируем данные
            async def export():
                results = await export_service.export_approved_data(
                    approved_data=approved_data,
                    original_filename=original_filename
                )
                return results

            results = asyncio.run(export())

            # Выводим результаты
            print(f"{'=' * 60}")
            print("Export Results:")
            print(f"{'=' * 60}\n")

            if results.get('excel', {}).get('success'):
                print(f"✓ Local Excel exported: {results['excel']['path']}")
            elif results.get('excel', {}).get('error'):
                print(f"✗ Local Excel export failed: {results['excel']['error']}")

            if results.get('sheets', {}).get('success'):
                print(f"✓ Online Excel (Google Sheets) exported successfully")
            elif results.get('sheets', {}).get('error'):
                print(f"✗ Online Excel (Google Sheets) export failed: {results['sheets']['error']}")

            print(f"\n{'=' * 60}\n")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            logger.error(f"Approve command failed: {e}", exc_info=True)
            sys.exit(1)


def main(args: Optional[list] = None):
    """
    Точка входа для CLI приложения

    Args:
        args: Аргументы командной строки
    """
    try:
        # Загрузка конфигурации
        config = Config.load()

        # Создание и запуск приложения
        app = CLIApp(config)
        app.run(args)

    except Exception as e:
        print(f"\nFatal error: {e}")
        logger.error(f"CLI app failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
