#!/usr/bin/env python3
"""
Пост-обработка: Склеивает артикулы, разделённые на UKT и Oboznachennya
"""

import xlrd
from xlutils.copy import copy as xl_copy
import sys

def fix_split_articles(input_file, output_file=None):
    """
    Исправляет артикулы, где дополнительные цифры попали в колонку обозначения
    """
    if output_file is None:
        output_file = input_file

    # Открываем файл
    rb = xlrd.open_workbook(input_file, formatting_info=True)
    wb = xl_copy(rb)
    sheet = wb.get_sheet(0)
    rs = rb.sheet_by_index(0)

    fixed_count = 0

    print(f"Обработка: {input_file}")
    print(f"Строк: {rs.nrows}")

    # Проходим по всем строкам (кроме заголовка)
    for row in range(1, rs.nrows):
        ukt = rs.cell_value(row, 6)  # УКТ ЗЕД
        oboz = rs.cell_value(row, 8)  # обозначение товара

        # Если артикул заканчивается на .00 и обозначение - это цифра
        if isinstance(ukt, str) and isinstance(oboz, str):
            # Проверяем, является ли обозначение просто цифрой или дополнением к артикулу
            if oboz and len(oboz) <= 3 and oboz.replace('-', '').isdigit():
                # Это похоже на продолжение артикула
                new_ukt = ukt + oboz
                sheet.write(row, 6, new_ukt)
                sheet.write(row, 8, '')  # Очищаем обозначение

                print(f"  Row {row}: {ukt} + {oboz} → {new_ukt}")
                fixed_count += 1

    # Сохраняем
    wb.save(output_file)
    print(f"\n✓ Исправлено {fixed_count} артикулов")
    print(f"💾 Сохранено: {output_file}")

    return fixed_count


def verify_results(file_path):
    """
    Проверяет результаты
    """
    wb = xlrd.open_workbook(file_path)
    sheet = wb.sheet_by_index(0)

    print(f"\n📊 Проверка результатов:")
    print(f"Первые 10 артикулов:")

    for i in range(1, min(11, sheet.nrows)):
        ukt = sheet.cell_value(i, 6)
        name = sheet.cell_value(i, 7)
        oboz = sheet.cell_value(i, 8)

        # Проверка на подозрительные артикулы
        warning = ""
        if isinstance(ukt, str) and ukt.endswith('.00') and not oboz:
            warning = " ⚠️"

        print(f"  {i}. {ukt}{warning}")
        if oboz:
            print(f"      Обозначение: {oboz}")


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python3 fix_articles.py <input.xls> [output.xls]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else input_file

    # Исправляем
    fixed_count = fix_split_articles(input_file, output_file)

    # Проверяем
    if fixed_count > 0:
        verify_results(output_file)


if __name__ == "__main__":
    main()
