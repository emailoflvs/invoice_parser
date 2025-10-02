#!/usr/bin/env python3
"""
Ручне виправлення першого артикулу на основі скріншоту користувача
"""

import xlrd
from xlutils.copy import copy as xl_copy

def fix_first_article():
    """
    Виправляє перший артикул: 521.318.01.04.06.00 → 521.318.01.04.06.001
    """
    file_path = "таблиця накладних.xls"

    # Відкриваємо файл
    rb = xlrd.open_workbook(file_path, formatting_info=True)
    wb = xl_copy(rb)
    sheet = wb.get_sheet(0)
    rs = rb.sheet_by_index(0)

    # Поточне значення
    current_article = rs.cell_value(1, 6)  # Рядок 1, колонка 6 (УКТ ЗЕД)

    print(f"Поточний артикул: {current_article}")

    # Перевірка чи потрібно виправлення
    if current_article == "521.318.01.04.06.00":
        # Виправляємо на основі скріншоту користувача
        new_article = "521.318.01.04.06.001"
        sheet.write(1, 6, new_article)
        wb.save(file_path)

        print(f"✓ Виправлено: {current_article} → {new_article}")

        # Перевірка
        rb2 = xlrd.open_workbook(file_path)
        ws2 = rb2.sheet_by_index(0)
        verified = ws2.cell_value(1, 6)
        print(f"✓ Перевірка: {verified}")
    else:
        print("⚠ Артикул вже має інше значення, не виправляю")

if __name__ == "__main__":
    fix_first_article()
