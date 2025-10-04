#!/usr/bin/env python3
"""
Улучшенный парсер накладных с постобработкой для исправления разорванных артикулов.
Использует Claude Sonnet 4 + логику постобработки для склейки переносов строк.
"""

import json
import sys
import anthropic
import os
import base64
from pathlib import Path
import xlwt
import re

def fix_split_articles(data: dict) -> dict:
    """
    Постобработка для исправления разорванных артикулов.

    Проблема: Claude иногда разрывает артикулы типа "521.318.01.04.06.00\n1"
    на ukt_zed="521.318.01.04.06.00" и oboznachennya_tovara="1"

    Решение: Если oboznachennya_tovara содержит только 1-3 символа (цифры/дефис),
    это продолжение артикула - склеиваем с ukt_zed.
    """
    items = data.get('items', [])

    for item in items:
        ukt_zed = item.get('ukt_zed', '').strip()
        oboznachennya = item.get('oboznachennya_tovara', '').strip()

        # Проверяем: если oboznachennya короткое (1-3 символа) и содержит только цифры/дефис
        if oboznachennya and len(oboznachennya) <= 3:
            # Проверяем что это похоже на продолжение артикула
            if re.match(r'^[\d\-]+$', oboznachennya):
                # Это продолжение артикула - склеиваем
                if ukt_zed:
                    item['ukt_zed'] = ukt_zed + oboznachennya
                    item['oboznachennya_tovara'] = ""
                    print(f"  Исправлен артикул: {ukt_zed} + {oboznachennya} → {item['ukt_zed']}")

        # Дополнительная проверка: если ukt_zed заканчивается на "00" или "."
        # и oboznachennya начинается с цифры - вероятно это продолжение
        if ukt_zed and oboznachennya:
            if (ukt_zed.endswith('00') or ukt_zed.endswith('.')) and oboznachennya[0].isdigit():
                if len(oboznachennya) <= 5:  # Не более 5 символов
                    item['ukt_zed'] = ukt_zed + oboznachennya
                    item['oboznachennya_tovara'] = ""
                    print(f"  Исправлен артикул (паттерн 00): {ukt_zed} + {oboznachennya} → {item['ukt_zed']}")

    return data


def parse_invoice_complete(pdf_path: str) -> dict:
    """
    Парсит PDF инвойс и возвращает JSON с реквизитами и товарами.
    Использует усиленный промпт и постобработку.
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY не установлен")

    client = anthropic.Anthropic(api_key=api_key)

    # Читаем PDF файл
    with open(pdf_path, 'rb') as f:
        pdf_data = f.read()

    pdf_base64 = base64.standard_b64encode(pdf_data).decode('utf-8')

    # Загружаем усиленный промпт
    with open('task-items-advanced.txt', 'r', encoding='utf-8') as f:
        items_prompt = f.read()

    print(f"Извлечение данных из PDF...")

    items_response_text = ""

    with client.messages.stream(
        model="claude-sonnet-4-20250514",
        max_tokens=64000,  # Увеличили до 64k для больших документов
        system=items_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_base64
                        }
                    }
                ]
            }
        ],
        timeout=600.0
    ) as stream:
        for text in stream.text_stream:
            items_response_text += text
            print(".", end="", flush=True)

    print()

    # Парсим JSON
    try:
        json_start = items_response_text.find('{')
        json_end = items_response_text.rfind('}') + 1
        json_str = items_response_text[json_start:json_end]
        data = json.loads(json_str)

        # Сохраняем сырой результат для отладки
        debug_file = f"{pdf_path}.raw_result.json"
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Отладка: сырой результат сохранен в {debug_file}")

        # Применяем постобработку для исправления разорванных артикулов
        print(f"Постобработка: исправление разорванных артикулов...")
        data = fix_split_articles(data)

        # Сохраняем исправленный результат
        fixed_debug_file = f"{pdf_path}.fixed_result.json"
        with open(fixed_debug_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Отладка: исправленный результат сохранен в {fixed_debug_file}")

        return data

    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        print(f"Ответ: {items_response_text[:500]}...")
        return {"header": {}, "items": [], "error": str(e)}


def export_to_excel_advanced(data: dict, excel_file: str, pdf_filename: str):
    """
    Экспортирует данные в расширенный формат Excel с реквизитами поставщика
    """
    # Проверяем, существует ли файл
    if Path(excel_file).exists():
        import xlrd
        from xlutils.copy import copy as xl_copy

        try:
            rb = xlrd.open_workbook(excel_file, formatting_info=True)
            wb = xl_copy(rb)
            sheet = wb.get_sheet(0)
            start_row = rb.sheet_by_index(0).nrows
        except:
            wb = xlwt.Workbook(encoding='utf-8')
            sheet = wb.add_sheet('Товары')
            start_row = 0
    else:
        wb = xlwt.Workbook(encoding='utf-8')
        sheet = wb.add_sheet('Товары')
        start_row = 0

    # Стили
    header_style = xlwt.easyxf('font: bold 1; align: horiz center')
    normal_style = xlwt.easyxf()

    # Если это первая запись, добавляем заголовки
    if start_row == 0:
        headers = [
            'постачальник',
            'код ЄДРПОУ',
            'телефон',
            'адреса',
            'дата накладної',
            'номер накладної',
            'УКТ ЗЕД',
            'наименование товара',
            'обозначение товара (номенклатура, артикль)',
            'ціна за шт без пдв',
            'кіл-сть штук',
            'сума без пдв',
            'ціна за одиницю з ПДВ',
            'сума з ПДВ'
        ]
        for col, header in enumerate(headers):
            sheet.write(0, col, header, header_style)
        start_row = 1

    # Получаем реквизиты поставщика
    header = data.get('header', {})
    postachalnyk = header.get('postachalnyk', '')
    kod_edrpu = header.get('kod_edrpu', '')
    telefon = header.get('telefon', '')
    adresa = header.get('adresa', '')
    data_nakladnoi = header.get('data_nakladnoi', '')
    nomer_nakladnoi = header.get('nomer_nakladnoi', '')

    # Добавляем данные о товарах
    items = data.get('items', [])

    for idx, item in enumerate(items):
        row = start_row + idx

        # Реквизиты поставщика (повторяются для каждого товара)
        sheet.write(row, 0, postachalnyk, normal_style)
        sheet.write(row, 1, kod_edrpu, normal_style)
        sheet.write(row, 2, telefon, normal_style)
        sheet.write(row, 3, adresa, normal_style)
        sheet.write(row, 4, data_nakladnoi, normal_style)
        sheet.write(row, 5, nomer_nakladnoi, normal_style)

        # Данные товара
        sheet.write(row, 6, item.get('ukt_zed', ''), normal_style)
        sheet.write(row, 7, item.get('naimenovanie_tovara', ''), normal_style)
        sheet.write(row, 8, item.get('oboznachennya_tovara', ''), normal_style)
        sheet.write(row, 9, item.get('tsina_za_sht_bez_pdv', ''), normal_style)
        sheet.write(row, 10, item.get('kilkist_shtuk', ''), normal_style)
        sheet.write(row, 11, item.get('suma_bez_pdv', ''), normal_style)
        sheet.write(row, 12, item.get('tsina_za_odynytsyu_z_pdv', ''), normal_style)
        sheet.write(row, 13, item.get('suma_z_pdv', ''), normal_style)

    # Сохраняем файл
    wb.save(excel_file)
    print(f"✓ Экспортировано {len(items)} товаров в {excel_file}")


def process_invoice(pdf_path: str, excel_file: str = "таблиця накладних.xls"):
    """
    Обрабатывает один инвойс: парсит и экспортирует в Excel
    """
    print(f"\n{'='*60}")
    print(f"Обработка: {pdf_path}")
    print(f"{'='*60}")

    # Парсим инвойс
    result = parse_invoice_complete(pdf_path)

    if 'error' in result:
        print(f"✗ Ошибка: {result['error']}")
        return result

    # Выводим краткую информацию
    header = result.get('header', {})
    items_count = len(result.get('items', []))

    print(f"\n📋 Реквизиты:")
    print(f"  Поставщик: {header.get('postachalnyk', 'N/A')}")
    print(f"  ЄДРПОУ: {header.get('kod_edrpu', 'N/A')}")
    print(f"  Дата: {header.get('data_nakladnoi', 'N/A')}")
    print(f"  Номер: {header.get('nomer_nakladnoi', 'N/A')}")
    print(f"\n📦 Товаров: {items_count}")

    # Экспортируем в Excel
    pdf_filename = Path(pdf_path).name
    export_to_excel_advanced(result, excel_file, pdf_filename)

    return result


def process_multiple_invoices(pdf_paths: list, excel_file: str = "таблиця накладних.xls"):
    """
    Обрабатывает несколько инвойсов
    """
    total_items = 0
    success_count = 0
    failed_count = 0

    for pdf_path in pdf_paths:
        try:
            result = process_invoice(pdf_path, excel_file)
            if 'error' not in result:
                total_items += len(result.get('items', []))
                success_count += 1
            else:
                failed_count += 1
        except Exception as e:
            print(f"✗ Ошибка при обработке {pdf_path}: {e}\n")
            failed_count += 1

    print(f"\n{'='*60}")
    print(f"📊 ИТОГИ")
    print(f"{'='*60}")
    print(f"✓ Успешно обработано: {success_count} файлов")
    print(f"✗ Ошибок: {failed_count}")
    print(f"📦 Всего товаров: {total_items}")
    print(f"💾 Результаты: {excel_file}")
    print(f"{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 invoice_parser_enhanced.py <путь_к_pdf> [output.xls]")
        print("  python3 invoice_parser_enhanced.py <путь1.pdf> <путь2.pdf> ... [output.xls]")
        print("  python3 invoice_parser_enhanced.py invoices/*.pdf")
        sys.exit(1)

    # Определяем выходной файл Excel
    excel_file = "таблиця накладних.xls"
    pdf_paths = []

    for arg in sys.argv[1:]:
        if arg.endswith('.xls'):
            excel_file = arg
        else:
            pdf_paths.append(arg)

    # Проверяем существование файлов
    valid_paths = []
    for pdf_path in pdf_paths:
        if Path(pdf_path).exists():
            valid_paths.append(pdf_path)
        else:
            print(f"⚠ Предупреждение: файл не найден: {pdf_path}")

    if not valid_paths:
        print("✗ Ошибка: не найдено ни одного валидного PDF файла")
        sys.exit(1)

    # Обрабатываем файлы
    if len(valid_paths) == 1:
        process_invoice(valid_paths[0], excel_file)
    else:
        process_multiple_invoices(valid_paths, excel_file)


if __name__ == "__main__":
    main()
