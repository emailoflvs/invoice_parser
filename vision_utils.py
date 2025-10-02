"""
Утилиты для работы с Google Vision API и группировки слов в ячейки таблицы
"""

from typing import List, Dict, Tuple
import statistics


def group_words_into_table_cells(words: List[Dict]) -> List[Dict]:
    """
    Группирует слова в ячейки таблицы на основе координат.

    Args:
        words: Список словарей с ключами: 'text', 'bbox' (x, y, width, height), 'page'

    Returns:
        Список ячеек с содержимым: [{'text': 'content', 'row': N, 'col': M, 'page': P}]
    """
    if not words:
        return []

    # Группируем слова по страницам
    pages = {}
    for word in words:
        page_num = word['page']
        if page_num not in pages:
            pages[page_num] = []
        pages[page_num].append(word)

    all_cells = []

    for page_num in sorted(pages.keys()):
        page_words = pages[page_num]
        page_cells = _process_page_words(page_words, page_num)
        all_cells.extend(page_cells)

    return all_cells


def _process_page_words(words: List[Dict], page_num: int) -> List[Dict]:
    """
    Обрабатывает слова одной страницы и группирует их в ячейки.
    """
    # Сортируем по Y (сверху вниз), затем по X (слева направо)
    sorted_words = sorted(words, key=lambda w: (w['bbox'][1], w['bbox'][0]))

    # Группируем в строки (по Y-координате)
    rows = _group_into_rows(sorted_words)

    # Определяем колонки (по X-координатам)
    columns = _detect_columns(rows)

    # Группируем в ячейки таблицы
    cells = _group_into_cells(rows, columns, page_num)

    return cells


def _group_into_rows(words: List[Dict], y_tolerance: int = 10) -> List[List[Dict]]:
    """
    Группирует слова в строки на основе Y-координаты.
    Слова с близкими Y (±y_tolerance) считаются одной строкой.
    """
    if not words:
        return []

    rows = []
    current_row = [words[0]]
    prev_y = words[0]['bbox'][1]

    for word in words[1:]:
        y = word['bbox'][1]

        # Если Y-координата близка к предыдущей - та же строка
        if abs(y - prev_y) <= y_tolerance:
            current_row.append(word)
        else:
            # Новая строка
            rows.append(current_row)
            current_row = [word]
            prev_y = y

    # Добавляем последнюю строку
    if current_row:
        rows.append(current_row)

    # Сортируем слова внутри каждой строки по X
    for row in rows:
        row.sort(key=lambda w: w['bbox'][0])

    return rows


def _detect_columns(rows: List[List[Dict]], x_tolerance: int = 50) -> List[Tuple[int, int]]:
    """
    Определяет колонки таблицы на основе X-координат слов во всех строках.

    Returns:
        Список диапазонов X-координат для каждой колонки: [(x_min, x_max), ...]
    """
    if not rows:
        return []

    # Собираем все X-координаты начала слов
    all_x_starts = []
    for row in rows:
        for word in row:
            all_x_starts.append(word['bbox'][0])

    if not all_x_starts:
        return []

    # Сортируем X-координаты
    all_x_starts.sort()

    # Кластеризуем близкие X-координаты в колонки
    column_clusters = []
    current_cluster = [all_x_starts[0]]

    for x in all_x_starts[1:]:
        if x - current_cluster[-1] <= x_tolerance:
            current_cluster.append(x)
        else:
            column_clusters.append(current_cluster)
            current_cluster = [x]

    if current_cluster:
        column_clusters.append(current_cluster)

    # Для каждого кластера определяем диапазон
    columns = []
    for i, cluster in enumerate(column_clusters):
        x_min = min(cluster)
        # x_max - это начало следующего кластера или очень большое число
        if i < len(column_clusters) - 1:
            x_max = min(column_clusters[i + 1]) - 1
        else:
            x_max = max(all_x_starts) + 1000  # Большое число

        columns.append((x_min, x_max))

    return columns


def _group_into_cells(rows: List[List[Dict]], columns: List[Tuple[int, int]], page_num: int) -> List[Dict]:
    """
    Группирует слова из строк в ячейки таблицы на основе колонок.
    """
    cells = []

    for row_idx, row in enumerate(rows):
        # Группируем слова текущей строки по колонкам
        row_cells = [[] for _ in columns]

        for word in row:
            word_x = word['bbox'][0]

            # Определяем, в какую колонку попадает слово
            for col_idx, (x_min, x_max) in enumerate(columns):
                if x_min <= word_x <= x_max:
                    row_cells[col_idx].append(word)
                    break

        # Создаем ячейки для текущей строки
        for col_idx, cell_words in enumerate(row_cells):
            if cell_words:
                cell_text = merge_cell_content(cell_words)
                cells.append({
                    'text': cell_text,
                    'row': row_idx,
                    'col': col_idx,
                    'page': page_num,
                    'words': cell_words  # Для отладки
                })

    return cells


def merge_cell_content(cell_words: List[Dict], is_numeric: bool = None) -> str:
    """
    Склеивает текст слов внутри одной ячейки.

    Args:
        cell_words: Список слов в ячейке
        is_numeric: Если True - склеиваем без пробелов (для артикулов и чисел)
                   Если None - автоматически определяем

    Returns:
        Склеенный текст
    """
    if not cell_words:
        return ""

    # Автоматическое определение типа содержимого
    if is_numeric is None:
        # Проверяем первое слово
        first_text = cell_words[0]['text']
        # Если начинается с цифры или содержит точки/дефисы - это артикул/число
        is_numeric = (first_text and
                     (first_text[0].isdigit() or
                      '.' in first_text or
                      '-' in first_text or
                      ',' in first_text))

    # Сортируем слова по Y (сверху вниз), затем по X (слева направо)
    sorted_words = sorted(cell_words, key=lambda w: (w['bbox'][1], w['bbox'][0]))

    texts = [w['text'] for w in sorted_words]

    if is_numeric:
        # Для артикулов и чисел - склеиваем без пробелов
        return ''.join(texts)
    else:
        # Для текста - склеиваем через пробел
        return ' '.join(texts)


def format_cells_as_table_text(cells: List[Dict]) -> str:
    """
    Форматирует ячейки в текстовое представление таблицы с метками.
    Используется для передачи в LLM.

    Returns:
        Текст вида:
        [TABLE_ROW_START]
        [CELL]content1[/CELL]
        [CELL]content2[/CELL]
        [TABLE_ROW_END]
    """
    if not cells:
        return ""

    # Группируем ячейки по строкам
    rows_dict = {}
    for cell in cells:
        row_key = (cell['page'], cell['row'])
        if row_key not in rows_dict:
            rows_dict[row_key] = []
        rows_dict[row_key].append(cell)

    # Сортируем строки
    sorted_rows = sorted(rows_dict.items(), key=lambda x: x[0])

    # Форматируем
    lines = []
    for (page, row), row_cells in sorted_rows:
        # Сортируем ячейки в строке по колонкам
        row_cells.sort(key=lambda c: c['col'])

        lines.append("[TABLE_ROW_START]")
        for cell in row_cells:
            lines.append(f"[CELL]{cell['text']}[/CELL]")
        lines.append("[TABLE_ROW_END]")
        lines.append("")  # Пустая строка между рядами

    return '\n'.join(lines)


def extract_words_from_vision_response(vision_response: Dict) -> List[Dict]:
    """
    Извлекает слова с координатами из ответа Google Vision API.

    Args:
        vision_response: JSON ответ от Google Vision API

    Returns:
        Список словарей: [{'text': 'word', 'bbox': [x, y, w, h], 'page': 0}]
    """
    words = []

    # Google Vision возвращает структуру responses[0].fullTextAnnotation.pages
    try:
        full_text = vision_response['responses'][0].get('fullTextAnnotation', {})
        pages = full_text.get('pages', [])

        for page_idx, page in enumerate(pages):
            blocks = page.get('blocks', [])

            for block in blocks:
                paragraphs = block.get('paragraphs', [])

                for paragraph in paragraphs:
                    paragraph_words = paragraph.get('words', [])

                    for word in paragraph_words:
                        # Извлекаем текст слова
                        symbols = word.get('symbols', [])
                        word_text = ''.join([s.get('text', '') for s in symbols])

                        # Извлекаем координаты (bounding box)
                        bbox_data = word.get('boundingBox', {})
                        vertices = bbox_data.get('vertices', [])

                        if len(vertices) >= 4 and word_text.strip():
                            # Вычисляем bbox: x, y, width, height
                            x = vertices[0].get('x', 0)
                            y = vertices[0].get('y', 0)
                            x_max = vertices[2].get('x', x)
                            y_max = vertices[2].get('y', y)
                            width = x_max - x
                            height = y_max - y

                            words.append({
                                'text': word_text.strip(),
                                'bbox': [x, y, width, height],
                                'page': page_idx
                            })

    except (KeyError, IndexError) as e:
        print(f"⚠ Ошибка извлечения слов из Vision response: {e}")
        return []

    return words
