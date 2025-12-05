import json
import os
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Импортируем вашу функцию сравнения (я её немного адаптирую)
def compare_jsons(prog_data: Dict, chat_data: Dict, filename: str) -> List[str]:
    diffs = []

    # Убираем метаданные
    for k in ['test_results', '_meta']:
        prog_data.pop(k, None)
        chat_data.pop(k, None)

    # 1. Document Info
    p_doc = prog_data.get('document_info', {})
    c_doc = chat_data.get('document_info', {})

    # Сравниваем только критичные поля
    for k in ['document_date', 'document_number', 'currency']:
        v1, v2 = p_doc.get(k), c_doc.get(k)
        if v1 != v2:
             diffs.append(f"[{filename}] INFO mismatch '{k}': PROG='{v1}' vs CHAT='{v2}'")

    # 2. Table Items Count
    p_items = prog_data.get('table_data', {}).get('line_items', [])
    c_items = chat_data.get('table_data', {}).get('line_items', [])

    if len(p_items) != len(c_items):
        diffs.append(f"[{filename}] ROW COUNT mismatch: PROG={len(p_items)} vs CHAT={len(c_items)}")

    # 3. Deep Compare Items (Smart)
    # Пытаемся найти артикулы
    p_art_key = next((k for k in (p_items[0].keys() if p_items else []) if 'article' in k), 'article')
    c_art_key = next((k for k in (c_items[0].keys() if c_items else []) if 'article' in k), 'article')

    # Пытаемся найти количество
    p_qty_key = next((k for k in (p_items[0].keys() if p_items else []) if 'qty' in k or 'quantity' in k), 'quantity')
    c_qty_key = next((k for k in (c_items[0].keys() if c_items else []) if 'qty' in k or 'quantity' in k), 'quantity')

    min_len = min(len(p_items), len(c_items))

    for i in range(min_len):
        # Сравнение артикулов
        val_p = str(p_items[i].get(p_art_key, '')).strip()
        val_c = str(c_items[i].get(c_art_key, '')).strip()

        # Упрощенное сравнение (без пробелов и точек)
        val_p_clean = val_p.replace(' ', '').replace('.', '').replace('-', '')
        val_c_clean = val_c.replace(' ', '').replace('.', '').replace('-', '')

        if val_p_clean != val_c_clean:
             diffs.append(f"[{filename}] ROW {i+1} ARTICLE mismatch: PROG='{val_p}' vs CHAT='{val_c}'")

        # Сравнение количества
        qty_p = str(p_items[i].get(p_qty_key, '')).split()[0] # берем только число
        qty_c = str(c_items[i].get(c_qty_key, '')).split()[0]

        try:
            if float(qty_p.replace(',', '.')) != float(qty_c.replace(',', '.')):
                diffs.append(f"[{filename}] ROW {i+1} QTY mismatch: PROG='{qty_p}' vs CHAT='{qty_c}'")
        except:
            pass # Если не числа, пропускаем

    return diffs

def main():
    parser = argparse.ArgumentParser(description='Batch Compare JSON outputs')
    parser.add_argument('--prog_dir', required=True, help='Directory with Program outputs')
    parser.add_argument('--chat_dir', required=True, help='Directory with Chat (Golden) outputs')
    parser.add_argument('--report', default='BATCH_REPORT.md', help='Output report file')

    args = parser.parse_args()

    prog_path = Path(args.prog_dir)
    chat_path = Path(args.chat_dir)

    report_lines = []
    report_lines.append(f"# Отчет сравнения парсинга от {datetime.now()}")
    report_lines.append(f"- Program Dir: `{args.prog_dir}`")
    report_lines.append(f"- Chat Dir: `{args.chat_dir}`")
    report_lines.append("---")

    # Находим общие файлы (предполагаем, что имена совпадают или похожи)
    # Для простоты ищем файлы, где имя файла из чата содержится в имени файла программы или наоборот
    prog_files = list(prog_path.glob("*.json"))
    chat_files = list(chat_path.glob("*.json"))

    matched_pairs = []

    for cf in chat_files:
        # Простая эвристика: ищем файл программы, который начинается так же
        # Например: dnipromash...json
        base_name = cf.name.split('_gemini')[0] # 'dnipromash'

        matching_pf = None
        for pf in prog_files:
            if base_name in pf.name:
                matching_pf = pf
                break

        if matching_pf:
            matched_pairs.append((matching_pf, cf))
        else:
            report_lines.append(f"⚠️ Не найдена пара для чат-файла: {cf.name}")

    total_diffs = 0

    for prog_f, chat_f in matched_pairs:
        report_lines.append(f"\n## 📄 {prog_f.name}")
        try:
            with open(prog_f, 'r', encoding='utf-8') as f:
                p_data = json.load(f)
            with open(chat_f, 'r', encoding='utf-8') as f:
                c_data = json.load(f)

            diffs = compare_jsons(p_data, c_data, prog_f.name)

            if not diffs:
                report_lines.append("✅ **ИДЕАЛЬНОЕ СОВПАДЕНИЕ**")
            else:
                report_lines.append(f"❌ Найдено **{len(diffs)}** отличий:")
                for d in diffs:
                    report_lines.append(f"- {d}")
                total_diffs += len(diffs)

        except Exception as e:
            report_lines.append(f"🔥 Ошибка при сравнении: {e}")

    report_lines.append("\n---")
    report_lines.append(f"**Всего отличий по всем файлам: {total_diffs}**")

    with open(args.report, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))

    print(f"Отчет готов: {args.report}")

if __name__ == "__main__":
    main()


