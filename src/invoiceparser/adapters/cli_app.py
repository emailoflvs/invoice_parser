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

        # Команда test
        test_parser = subparsers.add_parser('test', help='Run tests against examples')
        test_parser.add_argument(
            '--output',
            type=str,
            help='Path to save test report'
        )

        # Команда info
        info_parser = subparsers.add_parser('info', help='Show configuration info')

        return parser

    def _handle_parse(self, args):
        """
        Обработка команды parse

        Args:
            args: Аргументы команды
        """
        document_path = Path(args.path)

        print(f"\n{'=' * 60}")
        print(f"Parsing document: {document_path}")
        print(f"{'=' * 60}\n")

        try:
            # Обработка документа
            result = self.orchestrator.process_document(document_path)

            # Вывод результата
            if result["success"]:
                print("✓ Document parsed successfully\n")
                print(f"Invoice Number: {result['data'].header.invoice_number}")
                print(f"Date: {result['data'].header.date}")
                print(f"Supplier: {result['data'].header.supplier_name}")
                print(f"Total Amount: {result['data'].header.total_amount}")
                print(f"Items: {len(result['data'].items)}")
                print(f"\nResults saved to: {self.config.output_dir}")
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

            # Генерация отчета
            if args.output:
                report_path = Path(args.output)
            else:
                report_path = self.config.output_dir / f"test_report_{results['timestamp']}.json"

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
        print(f"  Excel: {self.config.export_excel_enabled}")
        print(f"  CRM: {self.config.export_crm_enabled}")

        print(f"\n{'=' * 60}\n")


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
