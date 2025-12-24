"""
Автоматический визуальный тест фронтенда
Парсит документ через API, рендерит в браузере, делает скриншот и анализирует ошибки
"""
import pytest
import json
import httpx
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect
import time
import tempfile
import shutil

# Путь к тестовому документу
TEST_DOCUMENT = Path(__file__).parent.parent / "invoices" / "invoice.jpg"
SERVER_URL = "http://localhost:8000"
TEST_TOKEN_FILE = Path("/tmp/test_token.txt")


def get_auth_token() -> str:
    """Получить токен авторизации"""
    if TEST_TOKEN_FILE.exists():
        return TEST_TOKEN_FILE.read_text().strip()

    # Если токена нет, создаем тестового пользователя и логинимся
    # Это упрощенная версия - в реальности нужно использовать существующего пользователя
    raise FileNotFoundError(f"Token file not found: {TEST_TOKEN_FILE}. Please login first.")


def parse_document_via_api(document_path: Path, token: str) -> dict:
    """Парсит документ через API (как на скриншоте)"""
    with open(document_path, 'rb') as f:
        files = {'file': (document_path.name, f, 'image/jpeg')}
        headers = {'Authorization': f'Bearer {token}'}

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{SERVER_URL}/parse?mode=fast",
                headers=headers,
                files=files
            )
            response.raise_for_status()
            return response.json()


def save_frontend_files(page: Page, output_dir: Path):
    """Сохраняет HTML, CSS, JS фронтенда для анализа"""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Сохраняем HTML
    html_content = page.content()
    (output_dir / "rendered_page.html").write_text(html_content, encoding='utf-8')

    # Сохраняем computed styles для всех элементов таблицы
    styles = page.evaluate("""
        () => {
            const table = document.querySelector('.editable-items-table');
            if (!table) return null;

            const styles = {};
            const cells = table.querySelectorAll('th, td');
            cells.forEach((cell, idx) => {
                const computed = window.getComputedStyle(cell);
                styles[`cell_${idx}`] = {
                    width: computed.width,
                    minWidth: computed.minWidth,
                    maxWidth: computed.maxWidth,
                    overflow: computed.overflow,
                    textOverflow: computed.textOverflow,
                    whiteSpace: computed.whiteSpace,
                    textAlign: computed.textAlign,
                    padding: computed.padding,
                    className: cell.className,
                    textContent: cell.textContent?.substring(0, 50)
                };
            });
            return styles;
        }
    """)

    if styles:
        (output_dir / "computed_styles.json").write_text(
            json.dumps(styles, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

    # Сохраняем данные таблицы
    table_data = page.evaluate("""
        () => {
            const table = document.querySelector('.editable-items-table');
            if (!table) return null;

            const headers = Array.from(table.querySelectorAll('thead th')).map(th => th.textContent?.trim());
            const rows = [];

            table.querySelectorAll('tbody tr').forEach(tr => {
                const cells = Array.from(tr.querySelectorAll('td')).map(td => {
                    const input = td.querySelector('input, textarea');
                    return input ? input.value : td.textContent?.trim();
                });
                rows.push(cells);
            });

            return { headers, rows };
        }
    """)

    if table_data:
        (output_dir / "table_data.json").write_text(
            json.dumps(table_data, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )


def analyze_table_errors(page: Page) -> list:
    """Анализирует таблицу и находит ошибки"""
    errors = []
    warnings = []

    # Получаем полную информацию о таблице
    table_info = page.evaluate("""
        () => {
            const table = document.querySelector('.editable-items-table');
            if (!table) return null;

            const headers = Array.from(table.querySelectorAll('thead th')).map((th, idx) => ({
                index: idx,
                text: th.textContent?.trim() || '',
                className: th.className,
                computedStyle: {
                    width: window.getComputedStyle(th).width,
                    minWidth: window.getComputedStyle(th).minWidth,
                    overflow: window.getComputedStyle(th).overflow
                }
            }));

            const rows = [];
            table.querySelectorAll('tbody tr').forEach((tr, rowIdx) => {
                const cells = Array.from(tr.querySelectorAll('td')).map((td, cellIdx) => {
                    const input = td.querySelector('input, textarea');
                    const tagName = input ? input.tagName.toLowerCase() : null;
                    const value = input ? input.value : td.textContent?.trim();
                    const className = td.className;

                    return {
                        index: cellIdx,
                        tagName: tagName,
                        value: value || '',
                        valueLength: (value || '').length,
                        className: className,
                        computedStyle: {
                            width: window.getComputedStyle(td).width,
                            minWidth: window.getComputedStyle(td).minWidth,
                            overflow: window.getComputedStyle(td).overflow,
                            textOverflow: window.getComputedStyle(td).textOverflow,
                            whiteSpace: window.getComputedStyle(td).whiteSpace
                        },
                        inputStyle: input ? {
                            overflow: window.getComputedStyle(input).overflow,
                            textOverflow: window.getComputedStyle(input).textOverflow,
                            width: window.getComputedStyle(input).width
                        } : null
                    };
                });
                rows.push({ index: rowIdx, cells });
            });

            return { headers, rows, rowCount: rows.length };
        }
    """)

    if not table_info:
        errors.append("❌ Таблица не найдена на странице")
        return errors

    print(f"   📊 Найдено колонок: {len(table_info['headers'])}, строк: {table_info['rowCount']}")

    # 1. Проверка наличия колонки №
    no_header_idx = None
    for i, header in enumerate(table_info['headers']):
        if "№" in header['text'] or 'col-line-number' in header['className']:
            no_header_idx = i
            break

    if no_header_idx is None:
        errors.append("❌ Колонка '№' отсутствует в заголовке")
    else:
        print(f"   ✅ Колонка '№' найдена на позиции {no_header_idx}")

        # Проверяем что колонка заполнена
        if table_info['rows']:
            first_row = table_info['rows'][0]
            if no_header_idx < len(first_row['cells']):
                no_cell = first_row['cells'][no_header_idx]
                no_value = no_cell['value'].strip()

                if not no_value:
                    errors.append(f"❌ Колонка '№' пустая в первой строке")
                else:
                    print(f"   ✅ Колонка '№' заполнена: '{no_value}'")
            else:
                errors.append(f"❌ Колонка '№' (индекс {no_header_idx}) не найдена в первой строке")

    # 2. Проверка обрезанных чисел
    print("   🔍 Проверка числовых колонок...")
    for row in table_info['rows'][:3]:  # Проверяем первые 3 строки
        for cell in row['cells']:
            if 'col-numeric' in cell['className'] or 'col-code' in cell['className']:
                value = cell['value']

                # Проверяем overflow стиль input
                if cell['inputStyle']:
                    overflow = cell['inputStyle']['overflow']
                    if overflow != 'visible':
                        errors.append(f"❌ Input в {cell['className']} имеет overflow='{overflow}' вместо 'visible' (значение: '{value}')")

                    text_overflow = cell['inputStyle']['textOverflow']
                    if text_overflow == 'ellipsis':
                        errors.append(f"❌ Input имеет text-overflow='ellipsis' (обрезает текст) для значения: '{value}'")

                # Проверяем что длинные числа не обрезаны
                if value and len(value) > 0:
                    # Для кодов (УКТ ЗЕД) ожидаем длину >= 10
                    if 'col-code' in cell['className'] and len(value) < 10 and value.replace('.', '').replace(',', '').isdigit():
                        warnings.append(f"⚠️  Код товара кажется коротким: '{value}' (длина: {len(value)})")

                    # Для цен проверяем наличие десятичных знаков
                    if 'col-numeric' in cell['className']:
                        has_decimal = '.' in value or ',' in value
                        if not has_decimal and len(value) > 0:
                            # Может быть обрезано
                            try:
                                float_val = float(value.replace(',', '.').replace(' ', ''))
                                if float_val != int(float_val):
                                    warnings.append(f"⚠️  Цена без десятичных знаков (возможно обрезано): '{value}'")
                            except:
                                pass

    # 3. Проверка textarea для длинного текста
    print("   🔍 Проверка текстовых колонок...")
    for row in table_info['rows'][:3]:
        for cell in row['cells']:
            if 'col-text' in cell['className']:
                value = cell['value']
                tag_name = cell['tagName']

                if len(value) > 30:
                    if tag_name == 'input':
                        errors.append(f"❌ Длинный текст ({len(value)} символов) в input вместо textarea: '{value[:50]}...'")
                    elif tag_name == 'textarea':
                        print(f"   ✅ Длинный текст в textarea: {len(value)} символов")

    # 4. Проверка порядка колонок
    header_texts = [h['text'] for h in table_info['headers']]
    print(f"   📋 Порядок колонок на экране: {header_texts}")

    # Получаем ожидаемый порядок из данных (если есть column_order в window.appData)
    expected_order = page.evaluate("""
        () => {
            if (window.appData && window.appData.table_data && window.appData.table_data.column_order) {
                return window.appData.table_data.column_order;
            }
            if (window.appData && window.appData.column_order) {
                return window.appData.column_order;
            }
            return null;
        }
    """)

    if expected_order:
        print(f"   📋 Ожидаемый порядок из данных: {expected_order}")
        # Проверяем что порядок соответствует (учитывая что названия могут отличаться)
        if len(header_texts) != len(expected_order):
            warnings.append(f"⚠️  Количество колонок не совпадает: экран={len(header_texts)}, данные={len(expected_order)}")
    else:
        print(f"   ⚠️  column_order не найден в данных, проверяем только наличие '№'")

    # Проверяем что № идет первым
    if len(header_texts) > 0 and "№" not in header_texts[0] and no_header_idx != 0:
        errors.append(f"❌ Колонка '№' не первая. Порядок: {header_texts[:5]}")

    # 5. Проверка CSS стилей колонок (overflow: visible, правильные ширины)
    print("   🔍 Проверка CSS стилей колонок...")
    for header in table_info['headers']:
        min_width = header['computedStyle']['minWidth']
        overflow = header['computedStyle']['overflow']

        # Проверяем overflow для заголовков
        if overflow == 'hidden':
            errors.append(f"❌ Заголовок '{header['text']}' имеет overflow='hidden' (должен быть 'visible')")

        # Проверяем min-width для числовых/кодовых колонок
        if 'col-numeric' in header['className'] or 'col-code' in header['className']:
            if 'max-content' not in min_width and 'auto' not in min_width:
                warnings.append(f"⚠️  Колонка '{header['text']}' имеет min-width='{min_width}' (рекомендуется max-content для полного отображения)")

    # 6. Проверка что все значения полностью видны (не обрезаны)
    print("   🔍 Проверка видимости всех значений...")
    for row_idx, row in enumerate(table_info['rows'][:3]):
        for cell in row['cells']:
            if cell['value']:
                value = cell['value']

                # Проверяем overflow ячейки
                overflow = cell['computedStyle']['overflow']
                if overflow == 'hidden':
                    errors.append(f"❌ Ячейка имеет overflow='hidden' (обрезает текст): '{value[:30]}...'")

                # Проверяем text-overflow (не должно быть ellipsis)
                text_overflow = cell['computedStyle']['textOverflow']
                if text_overflow == 'ellipsis':
                    errors.append(f"❌ Ячейка имеет text-overflow='ellipsis' (обрезает текст): '{value[:30]}...'")

                # Проверяем overflow input/textarea элемента
                if cell['inputStyle']:
                    input_overflow = cell['inputStyle']['overflow']
                    if input_overflow != 'visible':
                        errors.append(f"❌ Input/textarea имеет overflow='{input_overflow}' вместо 'visible' (значение: '{value[:30]}...')")

                    input_text_overflow = cell['inputStyle']['textOverflow']
                    if input_text_overflow == 'ellipsis':
                        errors.append(f"❌ Input/textarea имеет text-overflow='ellipsis' (обрезает текст): '{value[:30]}...'")

                # Для числовых полей проверяем что значение не обрезано
                if 'col-numeric' in cell['className'] or 'col-code' in cell['className']:
                    # Проверяем что длинные числа полностью видны
                    clean_value = value.replace(' ', '').replace(',', '').replace('.', '')
                    if 'col-code' in cell['className'] and len(clean_value) < 10 and clean_value.isdigit():
                        errors.append(f"❌ Код товара обрезан (длина {len(clean_value)}, ожидается >= 10): '{value}'")

                    # Проверяем что decimal числа не потеряли знаки после запятой
                    if 'col-numeric' in cell['className']:
                        try:
                            if '.' in value or ',' in value:
                                # Есть десятичные знаки - хорошо
                                pass
                            else:
                                # Нет десятичных знаков - проверяем не целое ли это число
                                float_val = float(value.replace(',', '.').replace(' ', ''))
                                if float_val != int(float_val):
                                    errors.append(f"❌ Число потеряло десятичные знаки: '{value}' (ожидалось с десятичными)")
                        except:
                            pass

    if warnings:
        print(f"\n   ⚠️  Предупреждения ({len(warnings)}):")
        for warning in warnings:
            print(f"      {warning}")

    return errors


def test_frontend_visual_parsing():
    """Полный тест: парсинг через API + визуальная проверка фронтенда"""

    if not TEST_DOCUMENT.exists():
        pytest.skip(f"Test document not found: {TEST_DOCUMENT}")

    # Получаем токен
    try:
        token = get_auth_token()
    except FileNotFoundError:
        pytest.skip("Auth token not found. Please login first.")

    # Парсим документ через API (повторяем до успеха, максимум 3 попытки)
    document_id = None
    for attempt in range(3):
        print(f"\n📄 Парсинг документа: {TEST_DOCUMENT.name} (попытка {attempt + 1})")
        try:
            parse_result = parse_document_via_api(TEST_DOCUMENT, token)
            if parse_result.get('success'):
                document_id = parse_result.get('document_id')
                if document_id:
                    print(f"✅ Парсинг успешен. Document ID: {document_id}")
                    break
        except Exception as e:
            print(f"⚠️ Ошибка парсинга (попытка {attempt + 1}): {e}")
            if attempt < 2:
                import time
                time.sleep(5)  # Ждем перед следующей попыткой
                continue

    if not document_id:
        pytest.skip("Не удалось распарсить документ после 3 попыток. Попробуйте позже.")

    # Создаем временную директорию для сохранения фронтенда
    temp_dir = Path(tempfile.mkdtemp(prefix="frontend_test_"))

    try:
        # Открываем страницу в браузере
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={'width': 1920, 'height': 1080})
            page = context.new_page()

            # Устанавливаем токен через add_init_script (выполняется ДО загрузки страницы)
            print(f"🔐 Устанавливаю токен в localStorage браузера...")
            page.add_init_script(f"localStorage.setItem('authToken', '{token}');")

            # Переходим на страницу документа
            url = f"{SERVER_URL}/?document_id={document_id}"
            print(f"🌐 Открываю страницу: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)

            # Даем время на загрузку данных (API запрос может занять время)
            page.wait_for_timeout(2000)

            # Ждем загрузки таблицы
            table = page.locator('.editable-items-table')
            try:
                expect(table).to_be_visible(timeout=10000)
                print("✅ Таблица загружена")
                except Exception as e:
                    print(f"⚠️ Таблица не найдена: {e}")
                    # Сохраняем HTML и скриншот для анализа
                    html_content = page.content()
                    (temp_dir / "error_page.html").write_text(html_content, encoding='utf-8')

                    # Проверяем console errors
                    console_logs = []
                    for log_entry in page.evaluate("() => window.consoleErrors || []"):
                        console_logs.append(log_entry)

                    # Проверяем что на странице
                    page_body = page.locator('body').inner_text()
                    print(f"📄 Содержимое body (первые 500 символов): {page_body[:500]}")

                    page.screenshot(path=str(temp_dir / "error_no_table.png"), full_page=True)
                    print(f"💾 Скриншот и HTML сохранены в {temp_dir}")
                    pytest.fail(f"Таблица не отображается на странице. См. {temp_dir}/error_page.html")

            # Сохраняем фронтенд для анализа
            print(f"💾 Сохраняю фронтенд в: {temp_dir}")
            save_frontend_files(page, temp_dir)

            # Делаем скриншот
            screenshot_path = temp_dir / "table_screenshot.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"📸 Скриншот сохранен: {screenshot_path}")

            # Анализируем ошибки
            print("\n🔍 Анализ таблицы на ошибки...")
            errors = analyze_table_errors(page)

            # Сохраняем детальный отчет
            detailed_report = page.evaluate("""
                () => {
                    const table = document.querySelector('.editable-items-table');
                    if (!table) return null;

                    const report = {
                        headers: Array.from(table.querySelectorAll('thead th')).map(th => ({
                            text: th.textContent?.trim(),
                            className: th.className,
                            styles: {
                                width: window.getComputedStyle(th).width,
                                minWidth: window.getComputedStyle(th).minWidth,
                                overflow: window.getComputedStyle(th).overflow
                            }
                        })),
                        rows: Array.from(table.querySelectorAll('tbody tr')).map(tr =>
                            Array.from(tr.querySelectorAll('td')).map(td => {
                                const input = td.querySelector('input, textarea');
                                return {
                                    value: input ? input.value : td.textContent?.trim(),
                                    tagName: input ? input.tagName.toLowerCase() : null,
                                    className: td.className,
                                    styles: {
                                        width: window.getComputedStyle(td).width,
                                        minWidth: window.getComputedStyle(td).minWidth,
                                        overflow: window.getComputedStyle(td).overflow,
                                        textOverflow: window.getComputedStyle(td).textOverflow
                                    },
                                    inputStyles: input ? {
                                        overflow: window.getComputedStyle(input).overflow,
                                        textOverflow: window.getComputedStyle(input).textOverflow,
                                        width: window.getComputedStyle(input).width
                                    } : null
                                };
                            })
                        )
                    };
                    return report;
                }
            """)

            if detailed_report:
                (temp_dir / "detailed_table_report.json").write_text(
                    json.dumps(detailed_report, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )

            if errors:
                print("\n❌ НАЙДЕНЫ ОШИБКИ:")
                for error in errors:
                    print(f"  {error}")

                # Сохраняем отчет об ошибках
                error_report = {
                    'document_id': document_id,
                    'errors': errors,
                    'screenshot': str(screenshot_path),
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'table_info': detailed_report
                }
                (temp_dir / "error_report.json").write_text(
                    json.dumps(error_report, indent=2, ensure_ascii=False),
                    encoding='utf-8'
                )

                pytest.fail(f"Найдено {len(errors)} ошибок. См. {temp_dir}")
            else:
                print("\n✅ Ошибок не найдено!")

            browser.close()

            # Выводим путь к сохраненным файлам
            print(f"\n📁 Все файлы сохранены в: {temp_dir}")
            print(f"   - rendered_page.html - полный HTML")
            print(f"   - table_data.json - данные таблицы")
            print(f"   - computed_styles.json - computed стили")
            print(f"   - table_screenshot.png - скриншот")

    finally:
        # НЕ удаляем temp_dir - оставляем для анализа
        print(f"\n💡 Временная директория сохранена: {temp_dir}")
        print(f"   Удалите вручную после анализа: rm -rf {temp_dir}")

