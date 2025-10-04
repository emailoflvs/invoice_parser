#!/usr/bin/env python3
"""
Парсер накладных с использованием Google Vision API для OCR и OpenAI для структурного парсинга.
Решает проблему переносов строк внутри ячеек таблиц за счет анализа координат слов.
"""

import json
import sys
import os
import base64
from pathlib import Path
import xlwt
from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_path
import requests
from vision_utils import (
    extract_words_from_vision_response,
    group_words_into_table_cells,
    format_cells_as_table_text
)

# Загружаем переменные окружения
load_dotenv()


def extract_text_with_google_vision(pdf_path: str) -> str:
    """
    Извлекает текст из PDF используя Google Vision API с сохранением структуры таблиц.

    Args:
        pdf_path: Путь к PDF файлу

    Returns:
        Форматированный текст с метками ячеек таблицы
    """
    api_key = os.getenv('GOOGLE_VISION_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_VISION_API_KEY не установлен в .env")

    print(f"Конвертация PDF в изображения...")
    # Конвертируем PDF в изображения
    images = convert_from_path(pdf_path, dpi=150)
    print(f"Конвертировано {len(images)} страниц")

    all_words = []

    # Обрабатываем каждую страницу
    for page_idx, image in enumerate(images):
        print(f"OCR страницы {page_idx + 1}/{len(images)}...", end=" ", flush=True)

        # Конвертируем изображение в base64
        import io
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

        # Формируем запрос к Google Vision API
        url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"

        payload = {
            "requests": [
                {
                    "image": {
                        "content": img_base64
                    },
                    "features": [
                        {
                            "type": "DOCUMENT_TEXT_DETECTION"
                        }
                    ]
                }
            ]
        }

        # Отправляем запрос
        try:
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            vision_response = response.json()

            # Извлекаем слова с координатами
            page_words = extract_words_from_vision_response(vision_response)

            # Корректируем номер страницы
            for word in page_words:
                word['page'] = page_idx

            all_words.extend(page_words)

            print(f"✓ Извлечено {len(page_words)} слов")

        except requests.exceptions.RequestException as e:
            print(f"✗ Ошибка: {e}")
            # Пытаемся извлечь детали ошибки из ответа
            try:
                error_detail = response.json()
                print(f"   Детали: {error_detail}")
            except:
                pass
            continue

    print(f"Всего извлечено {len(all_words)} слов со всех страниц")

    # Сохраняем слова для отладки
    debug_file = f"{pdf_path}.vision_words.json"
    with open(debug_file, 'w', encoding='utf-8') as f:
        json.dump(all_words, f, ensure_ascii=False, indent=2)
    print(f"Отладка: слова сохранены в {debug_file}")

    # Группируем слова в ячейки таблицы
    print(f"Группировка слов в ячейки таблицы...")
    cells = group_words_into_table_cells(all_words)
    print(f"Создано {len(cells)} ячеек таблицы")

    # Сохраняем ячейки для отладки
    debug_cells_file = f"{pdf_path}.grouped_cells.json"
    with open(debug_cells_file, 'w', encoding='utf-8') as f:
        json.dump(cells, f, ensure_ascii=False, indent=2)
    print(f"Отладка: ячейки сохранены в {debug_cells_file}")

    # Форматируем ячейки в текст для LLM
    formatted_text = format_cells_as_table_text(cells)

    # Сохраняем форматированный текст для отладки
    debug_text_file = f"{pdf_path}.formatted_text.txt"
    with open(debug_text_file, 'w', encoding='utf-8') as f:
        f.write(formatted_text)
    print(f"Отладка: форматированный текст сохранен в {debug_text_file}")

    return formatted_text


def parse_with_openai(formatted_text: str, prompt_file: str) -> dict:
    """
    Парсит форматированный текст с помощью OpenAI GPT-4o.

    Args:
        formatted_text: Текст с метками ячеек таблицы
        prompt_file: Путь к файлу с промптом

    Returns:
        Словарь с данными: {'header': {...}, 'items': [...]}
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY не установлен в .env")

    client = OpenAI(api_key=api_key)

    # Загружаем промпт
    with open(prompt_file, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    print(f"Отправка в OpenAI GPT-4o для парсинга...")

    try:
        # Используем GPT-4o для парсинга
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract data from this document:\n\n{formatted_text}"}
            ],
            temperature=0,
            max_tokens=16000,
            timeout=120.0
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
            print(f"⚠ Ошибка парсинга JSON: {e}")
            print(f"Ответ: {response_text[:500]}...")
            return {"header": {}, "items": [], "error": str(e)}

    except Exception as e:
        print(f"⚠ Ошибка OpenAI API: {e}")
        return {"header": {}, "items": [], "error": str(e)}


def parse_invoice_complete(pdf_path: str) -> dict:
    """
    Полный цикл парсинга накладной:
    1. OCR через Google Vision (с координатами)
    2. Группировка слов в ячейки таблицы
    3. Парсинг структурированного текста через OpenAI

    Args:
        pdf_path: Путь к PDF файлу

    Returns:
        Словарь с данными: {'header': {...}, 'items': [...]}
    """
    # Шаг 1: Извлекаем текст с Google Vision и группируем в ячейки
    formatted_text = extract_text_with_google_vision(pdf_path)

    # Шаг 2: Парсим с помощью OpenAI
    result = parse_with_openai(formatted_text, 'prompt-openai-simple.txt')

    # Сохраняем результат для отладки
    debug_json = f"{pdf_path}.result.json"
    with open(debug_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Отладка: результат сохранен в {debug_json}")

    return result


def export_to_excel_advanced(data: dict, excel_file: str, pdf_filename: str):
    """
    Экспортирует данные в расширенный формат Excel с реквизитами поставщика.
    (Переиспользован из invoice_parser.py)
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
    Обрабатывает один инвойс: парсит и экспортирует в Excel.
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
    Обрабатывает несколько инвойсов.
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
        print("  python3 invoice_parser_gvision.py <путь_к_pdf> [output.xls]")
        print("  python3 invoice_parser_gvision.py <путь1.pdf> <путь2.pdf> ... [output.xls]")
        print("  python3 invoice_parser_gvision.py invoices/*.pdf")
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
