#!/usr/bin/env python3
"""
Гибридный парсер накладных с извлечением реквизитов и товаров
Использует PyMuPDF для извлечения текста из PDF и OpenAI для парсинга
Экспорт в формат с полной информацией о поставщике в каждой строке
"""

import json
import sys
import os
from pathlib import Path
import xlwt
from dotenv import load_dotenv
from openai import OpenAI
import fitz  # PyMuPDF

# Загружаем переменные окружения
load_dotenv()


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Извлекает текст из PDF используя PyMuPDF с сохранением структуры
    """
    print(f"Извлечение текста из PDF...")
    doc = fitz.open(pdf_path)

    all_text = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        print(f"Обработка страницы {page_num + 1}/{len(doc)}...")

        # Извлекаем текст с сохранением структуры блоков
        # dict mode сохраняет информацию о блоках, что помогает с переносами
        text_dict = page.get_text("dict")

        page_lines = []
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # текстовый блок
                for line in block["lines"]:
                    line_text = ""
                    for span in line["spans"]:
                        line_text += span["text"]
                    if line_text.strip():
                        page_lines.append(line_text.strip())

        all_text.append('\n'.join(page_lines))

    doc.close()

    full_text = '\n\n=== НОВАЯ СТРАНИЦА ===\n\n'.join(all_text)
    print(f"Извлечено {len(full_text)} символов текста")

    return full_text


def parse_with_openai(text: str, prompt_file: str) -> dict:
    """
    Парсит извлеченный текст используя OpenAI
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY не установлен в .env")

    client = OpenAI(api_key=api_key)

    # Загружаем промпт
    with open(prompt_file, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    print(f"Отправка в OpenAI для парсинга...")

    # Используем GPT-4o для лучшего качества
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Вот текст документа:\n\n{text}"}
        ],
        temperature=0,
        max_tokens=16000
    )

    response_text = response.choices[0].message.content

    print(f"Получен ответ от OpenAI")

    # Парсим JSON из ответа
    try:
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)
        return data
    except Exception as e:
        print(f"⚠ Ошибка парсинга JSON: {e}", file=sys.stderr)
        print(f"Ответ: {response_text[:500]}...", file=sys.stderr)
        return {"header": {}, "items": [], "error": str(e)}


def parse_invoice_complete(pdf_path: str) -> dict:
    """
    Парсит PDF инвойс и возвращает JSON с реквизитами и товарами
    """
    # Шаг 1: Извлекаем текст из PDF
    text = extract_text_from_pdf(pdf_path)

    # Сохраняем извлеченный текст для отладки
    debug_file = f"{pdf_path}.extracted_text.txt"
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Отладка: текст сохранен в {debug_file}")

    # Шаг 2: Парсим с помощью OpenAI
    result = parse_with_openai(text, 'task-items-advanced.txt')

    # Сохраняем результат для отладки
    debug_json = f"{pdf_path}.result.json"
    with open(debug_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Отладка: результат сохранен в {debug_json}")

    return result


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
        print("  python3 invoice_parser_hybrid.py <путь_к_pdf> [output.xls]")
        print("  python3 invoice_parser_hybrid.py <путь1.pdf> <путь2.pdf> ... [output.xls]")
        print("  python3 invoice_parser_hybrid.py invoices/*.pdf")
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
