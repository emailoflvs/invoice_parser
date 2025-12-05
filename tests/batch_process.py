#!/usr/bin/env python3
"""
Батч-обработка документов из INVOICES_DIR с сравнением с эталонами
"""
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

# Добавляем путь к модулям
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.services.orchestrator import Orchestrator

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("batch_process")


def find_reference_file(invoice_name: str, examples_dir: Path) -> Optional[Path]:
    """
    Находит эталонный файл для сравнения

    Args:
        invoice_name: Базовое имя файла (без расширения)
        examples_dir: Директория с эталонами

    Returns:
        Путь к эталонному файлу или None
    """
    # Ищем файлы, которые начинаются с invoice_name
    # Например: dnipromash -> dnipromash_gemini_thinking_2_prompts_v7.json
    patterns = [
        f"{invoice_name}_gemini_thinking_2_prompts_v7.json",
        f"{invoice_name}_gemini_thinking_2_prompts_v*.json",
        f"{invoice_name}_*.json",
    ]

    for pattern in patterns:
        matches = list(examples_dir.glob(pattern))
        if matches:
            return matches[0]  # Возвращаем первый найденный

    return None


def compare_jsons(prog_data: Dict, chat_data: Dict, filename: str) -> List[Dict[str, Any]]:
    """
    Умное сравнение двух JSON файлов

    Args:
        prog_data: Данные из программы
        chat_data: Данные из чата (эталон)
        filename: Имя файла для логов

    Returns:
        Список различий
    """
    diffs = []

    # Убираем метаданные
    for k in ['test_results', '_meta']:
        prog_data.pop(k, None)
        chat_data.pop(k, None)

    # 1. Document Info
    p_doc = prog_data.get('document_info', {})
    c_doc = chat_data.get('document_info', {})

    for k in set(p_doc.keys()) | set(c_doc.keys()):
        v1, v2 = p_doc.get(k), c_doc.get(k)
        if v1 != v2:
            diffs.append({
                'type': 'document_info',
                'field': k,
                'program': v1,
                'reference': v2,
                'description': f"document_info.{k}: '{v1}' vs '{v2}'"
            })

    # 2. Parties structure
    p_parties = prog_data.get('parties', {})
    c_parties = chat_data.get('parties', {})

    if set(p_parties.keys()) != set(c_parties.keys()):
        diffs.append({
            'type': 'parties_structure',
            'field': 'roles',
            'program': list(p_parties.keys()),
            'reference': list(c_parties.keys()),
            'description': f"Different party roles: {list(p_parties.keys())} vs {list(c_parties.keys())}"
        })

    # Сравниваем customer (если есть)
    if 'customer' in p_parties and 'customer' in c_parties:
        p_cust = p_parties['customer']
        c_cust = c_parties['customer']
        for k in ['address', 'bank', 'name', 'edrpou', 'ipn']:
            if p_cust.get(k) != c_cust.get(k):
                diffs.append({
                    'type': 'parties_customer',
                    'field': k,
                    'program': p_cust.get(k),
                    'reference': c_cust.get(k),
                    'description': f"parties.customer.{k}: differs"
                })

    # 3. Table Items
    p_items = prog_data.get('table_data', {}).get('line_items', [])
    c_items = chat_data.get('table_data', {}).get('line_items', [])

    if len(p_items) != len(c_items):
        diffs.append({
            'type': 'table_count',
            'field': 'line_items',
            'program': len(p_items),
            'reference': len(c_items),
            'description': f"Row count: {len(p_items)} vs {len(c_items)}"
        })

    # Сравниваем структуру колонок
    if p_items and c_items:
        p_cols = set(p_items[0].keys())
        c_cols = set(c_items[0].keys())
        if p_cols != c_cols:
            diffs.append({
                'type': 'table_structure',
                'field': 'column_names',
                'program': list(p_cols),
                'reference': list(c_cols),
                'description': f"Different column structure: {list(p_cols)} vs {list(c_cols)}"
            })

        # Сравниваем артикулы (находим ключ для артикула)
        p_art_key = next((k for k in p_items[0].keys() if 'article' in k.lower() or 'art' in k.lower()), None)
        c_art_key = next((k for k in c_items[0].keys() if 'article' in k.lower() or 'art' in k.lower()), None)

        if p_art_key and c_art_key:
            art_diffs = 0
            for i in range(min(len(p_items), len(c_items))):
                val_p = str(p_items[i].get(p_art_key, '')).strip()
                val_c = str(c_items[i].get(c_art_key, '')).strip()

                # Нормализуем для сравнения (убираем пробелы, точки)
                val_p_clean = val_p.replace(' ', '').replace('.', '').replace('-', '')
                val_c_clean = val_c.replace(' ', '').replace('.', '').replace('-', '')

                if val_p_clean != val_c_clean:
                    art_diffs += 1
                    diffs.append({
                        'type': 'table_article',
                        'field': f'row_{i+1}',
                        'program': val_p,
                        'reference': val_c,
                        'description': f"Row {i+1} article mismatch: '{val_p}' vs '{val_c}'"
                    })

            if art_diffs > 0:
                logger.warning(f"{filename}: Found {art_diffs} article mismatches")

    return diffs


def process_batch():
    """Обработка всех файлов из INVOICES_DIR"""

    # Инициализация
    try:
        config = Config()
        orchestrator = Orchestrator(config)
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    invoices_dir = Path(config.invoices_dir)
    output_dir = Path(config.output_dir)
    examples_dir = Path(config.examples_dir) / "gemini_thinking_2_prompts_v7"

    if not invoices_dir.exists():
        logger.error(f"INVOICES_DIR not found: {invoices_dir}")
        sys.exit(1)

    if not examples_dir.exists():
        logger.warning(f"Examples dir not found: {examples_dir}")
        examples_dir = None

    # Находим все файлы для обработки
    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.bmp']
    invoice_files = []
    for ext in supported_extensions:
        invoice_files.extend(invoices_dir.glob(f"*{ext}"))
        invoice_files.extend(invoices_dir.glob(f"*{ext.upper()}"))

    if not invoice_files:
        logger.warning(f"No files found in {invoices_dir}")
        return

    logger.info(f"Found {len(invoice_files)} file(s) to process")

    # Отчет
    report = {
        'timestamp': datetime.now().isoformat(),
        'model': config.gemini_model,
        'total_files': len(invoice_files),
        'processed': [],
        'failed': [],
        'comparisons': []
    }

    # Обработка каждого файла
    for i, invoice_file in enumerate(invoice_files, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{i}/{len(invoice_files)}] Processing: {invoice_file.name}")
        logger.info(f"{'='*60}")

        try:
            # Ищем эталонный файл
            reference_file = None
            if examples_dir:
                reference_file = find_reference_file(invoice_file.stem, examples_dir)
                if reference_file:
                    logger.info(f"Found reference: {reference_file.name}")
                else:
                    logger.info("No reference file found")

            # Обработка документа
            result = orchestrator.process_document(invoice_file, compare_with=reference_file)

            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                logger.error(f"Failed: {error_msg}")
                report['failed'].append({
                    'file': invoice_file.name,
                    'error': error_msg
                })
                continue

            # Получаем путь к сохраненному файлу
            output_file = result.get("output_file")
            if output_file:
                output_path = Path(output_file)
            else:
                # Если файл не был сохранен автоматически, сохраняем вручную
                output_path = output_dir / f"{invoice_file.stem}_result.json"

            logger.info(f"✅ Saved to: {output_path.name}")

            # Сравнение с эталоном (если есть)
            comparison = None
            if reference_file:
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        prog_data = json.load(f)
                    with open(reference_file, 'r', encoding='utf-8') as f:
                        ref_data = json.load(f)

                    diffs = compare_jsons(prog_data, ref_data, invoice_file.name)

                    comparison = {
                        'file': invoice_file.name,
                        'reference': reference_file.name,
                        'differences_count': len(diffs),
                        'differences': diffs[:20]  # Первые 20 для отчета
                    }

                    if diffs:
                        logger.warning(f"⚠️  Found {len(diffs)} differences")
                    else:
                        logger.info("✅ Perfect match!")

                    report['comparisons'].append(comparison)

                except Exception as e:
                    logger.error(f"Comparison error: {e}")

            report['processed'].append({
                'file': invoice_file.name,
                'output': str(output_path),
                'elapsed_time': result.get("elapsed_time", 0),
                'comparison': comparison
            })

        except Exception as e:
            logger.error(f"Unexpected error processing {invoice_file.name}: {e}", exc_info=True)
            report['failed'].append({
                'file': invoice_file.name,
                'error': str(e)
            })

    # Сохранение отчета
    report_path = output_dir / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Создание текстового отчета
    report_txt_path = output_dir / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_txt_path, 'w', encoding='utf-8') as f:
        f.write(f"# Batch Processing Report\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Model:** {config.gemini_model}\n")
        f.write(f"**Total files:** {len(invoice_files)}\n")
        f.write(f"**Processed:** {len(report['processed'])}\n")
        f.write(f"**Failed:** {len(report['failed'])}\n\n")

        f.write("## Processed Files\n\n")
        for item in report['processed']:
            f.write(f"### {item['file']}\n")
            f.write(f"- Output: `{item['output']}`\n")
            f.write(f"- Time: {item['elapsed_time']:.2f}s\n")
            if item.get('comparison'):
                comp = item['comparison']
                f.write(f"- **Differences: {comp['differences_count']}**\n")
                if comp['differences']:
                    f.write("  - " + "\n  - ".join([d['description'] for d in comp['differences'][:10]]) + "\n")
            f.write("\n")

        if report['failed']:
            f.write("## Failed Files\n\n")
            for item in report['failed']:
                f.write(f"- **{item['file']}**: {item['error']}\n")
            f.write("\n")

        # Сводка по сравнениям
        if report['comparisons']:
            f.write("## Comparison Summary\n\n")
            total_diffs = sum(c['differences_count'] for c in report['comparisons'])
            f.write(f"**Total differences across all files: {total_diffs}**\n\n")

            for comp in report['comparisons']:
                if comp['differences_count'] > 0:
                    f.write(f"- **{comp['file']}**: {comp['differences_count']} differences\n")

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Batch processing completed!")
    logger.info(f"📊 Processed: {len(report['processed'])}")
    logger.info(f"❌ Failed: {len(report['failed'])}")
    logger.info(f"📄 Report: {report_path}")
    logger.info(f"📄 Report (MD): {report_txt_path}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    process_batch()


