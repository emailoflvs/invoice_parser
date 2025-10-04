#!/usr/bin/env python3
"""
Парсер накладных с улучшенной обработкой изображений.
1. Улучшение изображения (3x разрешение, контраст, яркость, резкость)
2. Google Vision API для OCR
3. OpenAI для извлечения заголовка (prompt-header.txt)
4. OpenAI для извлечения товаров (prompt-items.txt)
5. Экспорт в Excel
"""

import json
import sys
import os
import base64
import io
from pathlib import Path
import xlwt
from dotenv import load_dotenv
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image, ImageEnhance, ImageFilter
import requests

# Загружаем переменные окружения
load_dotenv()


def enhance_image(img: Image.Image) -> Image.Image:
    """
    Улучшает качество изображения для OCR:
    - 4x увеличение разрешения (для мелкого текста)
    - Повышение контраста на 100%
    - Повышение яркости на 40%
    - Максимальная резкость x5
    - Удаление шумов
    - Дополнительное усиление краев
    """
    # 1. Увеличиваем разрешение в 4 раза (для мелкого текста)
    scale_factor = 4
    new_size = (img.width * scale_factor, img.height * scale_factor)
    img = img.resize(new_size, Image.LANCZOS)

    # 2. RGB conversion
    if img.mode != 'RGB':
        img = img.convert('RGB')

    # 3. Увеличиваем контраст на 100%
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # 4. Повышаем яркость на 40%
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.4)

    # 5. Максимальная резкость x5
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(5.0)

    # 6. Удаляем шумы
    img = img.filter(ImageFilter.MedianFilter(size=3))

    # 7. Дополнительная резкость
    img = img.filter(ImageFilter.SHARPEN)

    # 8. Усиление краев для мелкого текста
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

    return img


def extract_text_with_google_vision(pdf_path: str) -> str:
    """
    Извлекает текст из PDF/JPG/PNG используя Google Vision API с улучшением изображения.
    """
    api_key = os.getenv('GOOGLE_VISION_API_KEY')
    if not api_key:
        raise ValueError("GOOGLE_VISION_API_KEY не установлен в .env")

    # Определяем тип файла
    file_ext = Path(pdf_path).suffix.lower()

    if file_ext in ['.jpg', '.jpeg', '.png']:
        # Если это изображение, загружаем его напрямую
        print(f"Загрузка изображения...")
        images = [Image.open(pdf_path)]
        print(f"Загружено 1 изображение")
    else:
        # Если это PDF, конвертируем в изображения
        print(f"Конвертация PDF в изображения...")
        images = convert_from_path(pdf_path, dpi=150)
        print(f"Конвертировано {len(images)} страниц")

    all_text = []

    for page_idx, image in enumerate(images):
        print(f"Обработка страницы {page_idx + 1}/{len(images)}...", end=" ", flush=True)

        # Улучшаем изображение
        enhanced_image = enhance_image(image)

        # Конвертируем изображение в base64
        img_byte_arr = io.BytesIO()
        enhanced_image.save(img_byte_arr, format='PNG')
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

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            vision_response = response.json()

            if 'error' in vision_response.get('responses', [{}])[0]:
                error = vision_response['responses'][0]['error']
                print(f"✗ Vision API error: {error.get('message', 'Unknown error')}")
                continue

            # Извлекаем полный текст
            text_annotation = vision_response['responses'][0].get('fullTextAnnotation', {})
            page_text = text_annotation.get('text', '')
            all_text.append(page_text)

            print(f"✓ Извлечено {len(page_text)} символов")

        except requests.exceptions.RequestException as e:
            print(f"✗ Ошибка: {e}")
            continue

    full_text = "\n\n".join(all_text)

    # Сохраняем текст для отладки
    debug_file = f"{pdf_path}.vision_text.txt"
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(full_text)
    print(f"Отладка: текст сохранен в {debug_file}")

    return full_text


def parse_header_with_openai(vision_text: str) -> dict:
    """
    Извлекает заголовок документа с помощью OpenAI GPT-4o.
    Использует промпт из prompt-header.txt.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY не установлен в .env")

    client = OpenAI(api_key=api_key)

    # Загружаем промпт для заголовка
    with open('prompt-header.txt', 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    print(f"Извлечение заголовка с OpenAI...", end=" ", flush=True)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": vision_text}
            ],
            temperature=0,
            max_tokens=4000,
            timeout=None
        )

        response_text = response.choices[0].message.content
        print(f"✓")

        # Парсим JSON из ответа
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            return data.get('header', {})
        except Exception as e:
            print(f"⚠ Ошибка парсинга JSON заголовка: {e}")
            return {}

    except Exception as e:
        print(f"✗ Ошибка OpenAI API: {e}")
        return {}


def parse_items_with_openai(vision_text: str) -> list:
    """
    Извлекает список товаров с помощью OpenAI GPT-4o.
    Использует промпт из prompt-items.txt.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OPENAI_API_KEY не установлен в .env")

    client = OpenAI(api_key=api_key)

    # Загружаем промпт для товаров
    with open('prompt-items.txt', 'r', encoding='utf-8') as f:
        system_prompt = f.read()

    print(f"Извлечение товаров с OpenAI...", end=" ", flush=True)

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": vision_text}
            ],
            temperature=0,
            max_tokens=16384,
            timeout=None
        )

        response_text = response.choices[0].message.content
        print(f"✓")

        # Парсим JSON из ответа
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            json_str = response_text[json_start:json_end]
            data = json.loads(json_str)
            items = data.get('items', [])
            print(f"  Найдено товаров: {len(items)}")
            return items
        except Exception as e:
            print(f"⚠ Ошибка парсинга JSON товаров: {e}")
            return []

    except Exception as e:
        print(f"✗ Ошибка OpenAI API: {e}")
        return []


def parse_invoice_complete(pdf_path: str) -> dict:
    """
    Полный цикл парсинга накладной:
    1. Улучшение изображения
    2. OCR через Google Vision
    3. Извлечение заголовка через OpenAI
    4. Извлечение товаров через OpenAI
    """
    # Шаг 1-2: Извлекаем текст с Google Vision (с улучшением изображения)
    vision_text = extract_text_with_google_vision(pdf_path)

    # Шаг 3: Извлекаем заголовок
    header = parse_header_with_openai(vision_text)

    # Шаг 4: Извлекаем товары
    items = parse_items_with_openai(vision_text)

    result = {
        'header': header,
        'items': items
    }

    # Сохраняем результат для отладки
    debug_json = f"{pdf_path}.result.json"
    with open(debug_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Отладка: результат сохранен в {debug_json}")

    return result


def export_to_excel_advanced(data: dict, excel_file: str, pdf_filename: str):
    """
    Экспортирует данные в расширенный формат Excel с реквизитами поставщика.
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
        print("  python3 invoice_parser_work_plan.py <путь_к_файлу> [output.xls]")
        print("  python3 invoice_parser_work_plan.py <файл1> <файл2> ... [output.xls]")
        print("  python3 invoice_parser_work_plan.py invoices/*.pdf")
        print("  python3 invoice_parser_work_plan.py invoices/*.jpg")
        print("\nПоддерживаемые форматы: PDF, JPG, PNG")
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
