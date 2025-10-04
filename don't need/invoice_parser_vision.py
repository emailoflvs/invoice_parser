#!/usr/bin/env python3
"""
Продвинутый парсер накладных с извлечением реквизитов и товаров
Использует OpenAI GPT-4o Vision для прямого парсинга PDF изображений
Экспорт в формат с полной информацией о поставщике в каждой строке
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

# Загружаем переменные окружения
load_dotenv()


def parse_pdf_with_openai_vision(pdf_path: str, prompt_file: str) -> dict:
    """
    Парсит PDF напрямую используя OpenAI Vision API (GPT-4o)
    Конвертирует PDF в изображения и отправляет партиями в OpenAI
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY не установлен в .env")

    client = OpenAI(api_key=api_key)

    # Загружаем промпт
    with open(prompt_file, 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    print(f"Конвертация PDF в изображения...")
    # Конвертируем PDF в изображения с низким разрешением для ускорения
    images = convert_from_path(pdf_path, dpi=100)
    print(f"Конвертировано {len(images)} страниц")

    # Обрабатываем по 3 страницы за раз для больших документов
    batch_size = 3
    all_items = []
    header = {}

    for batch_start in range(0, len(images), batch_size):
        batch_end = min(batch_start + batch_size, len(images))
        batch_images = images[batch_start:batch_end]

        print(f"\nОбработка страниц {batch_start + 1}-{batch_end} (партия {batch_start // batch_size + 1})...")

        # Кодируем изображения партии в base64
        image_messages = []
        for i, image in enumerate(batch_images):
            import io
            img_byte_arr = io.BytesIO()
            # Сжимаем изображение в JPEG с качеством 60% для уменьшения размера
            image.save(img_byte_arr, format='JPEG', quality=60, optimize=True)
            img_byte_arr = img_byte_arr.getvalue()

            size_kb = len(img_byte_arr) / 1024
            print(f"  Страница {batch_start + i + 1}: {size_kb:.1f} KB")

            img_base64 = base64.b64encode(img_byte_arr).decode('utf-8')

            image_messages.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{img_base64}",
                    "detail": "low"  # Используем low для экономии токенов
                }
            })

        # Добавляем текстовое сообщение
        messages_content = [
            {
                "type": "text",
                "text": "Проанализируй эти страницы документа (накладной/акта/инвойса) и извлеки информацию."
            }
        ] + image_messages

        print(f"  Отправка в OpenAI...")

        # Используем GPT-4o с vision
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": messages_content}
                ],
                temperature=0,
                max_tokens=16000,
                timeout=120.0  # 2 минуты таймаут
            )

            response_text = response.choices[0].message.content

            # Сохраняем ответ для отладки
            debug_file = f"{pdf_path}.batch_{batch_start // batch_size + 1}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response_text)

            # Парсим JSON из ответа
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            batch_data = json.loads(json_str)

            # Собираем данные
            if not header:
                header = batch_data.get('header', {})

            batch_items = batch_data.get('items', [])
            all_items.extend(batch_items)

            print(f"  ✓ Извлечено {len(batch_items)} товаров")

        except Exception as e:
            print(f"  ⚠ Ошибка обработки партии: {e}")
            continue

    return {
        "header": header,
        "items": all_items
    }


def parse_invoice_complete(pdf_path: str) -> dict:
    """
    Парсит PDF инвойс и возвращает JSON с реквизитами и товарами
    Использует OpenAI GPT-4o Vision для прямого анализа изображений
    """
    # Парсим напрямую через OpenAI Vision
    result = parse_pdf_with_openai_vision(pdf_path, 'task-items-advanced.txt')

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
        print("  python3 invoice_parser_vision.py <путь_к_pdf> [output.xls]")
        print("  python3 invoice_parser_vision.py <путь1.pdf> <путь2.pdf> ... [output.xls]")
        print("  python3 invoice_parser_vision.py invoices/*.pdf")
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
