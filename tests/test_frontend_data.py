"""
Упрощенный тест данных фронтенда (без браузера)
Парсит документ через API и проверяет структуру данных
"""
import pytest
import json
import httpx
from pathlib import Path
import tempfile

TEST_DOCUMENT = Path(__file__).parent.parent / "invoices" / "invoice.jpg"
SERVER_URL = "http://localhost:8000"
TEST_TOKEN_FILE = Path("/tmp/test_token.txt")


def get_auth_token() -> str:
    """Получить токен авторизации"""
    if TEST_TOKEN_FILE.exists():
        return TEST_TOKEN_FILE.read_text().strip()
    raise FileNotFoundError(f"Token file not found: {TEST_TOKEN_FILE}")


def parse_document_via_api(document_path: Path, token: str) -> dict:
    """Парсит документ через API"""
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


def get_document_data(document_id: int, token: str) -> dict:
    """Получает данные документа через API"""
    headers = {'Authorization': f'Bearer {token}'}

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{SERVER_URL}/api/documents/{document_id}",
            headers=headers
        )
        response.raise_for_status()
        return response.json()


def analyze_data_structure(data: dict) -> list:
    """Анализирует структуру данных на ошибки"""
    errors = []
    warnings = []

    # Извлекаем данные из структуры ответа API
    # API возвращает { "success": true, "data": { "table_data": {...} } }
    inner_data = data.get('data', data)  # Если data.data нет, используем сам data
    table_data = inner_data.get('table_data', {})
    if not table_data:
        errors.append("❌ table_data отсутствует в ответе")
        return errors

    # Проверяем column_order (может отсутствовать, тогда используем порядок ключей column_mapping)
    column_order = table_data.get('column_order', [])
    if column_order:
        print(f"   📋 column_order: {column_order}")

        # Проверяем что "no" есть в column_order
        if 'no' not in column_order:
            errors.append(f"❌ 'no' отсутствует в column_order: {column_order}")
        else:
            print(f"   ✅ 'no' найден в column_order на позиции {column_order.index('no')}")

        # Проверяем что служебные поля отфильтрованы
        service_fields = ['raw', '_meta', '_label']
        for field in service_fields:
            if field in column_order:
                errors.append(f"❌ Служебное поле '{field}' присутствует в column_order")
    else:
        # Если column_order нет, используем порядок ключей из column_mapping
        column_mapping = table_data.get('column_mapping', {})
        if column_mapping:
            column_order = list(column_mapping.keys())
            print(f"   📋 column_order отсутствует, используем порядок из column_mapping: {column_order}")
            if 'no' not in column_order:
                errors.append(f"❌ 'no' отсутствует в column_mapping: {column_order}")
            else:
                print(f"   ✅ 'no' найден в column_mapping на позиции {column_order.index('no')}")

    # Проверяем line_items
    line_items = table_data.get('line_items', [])
    if not line_items:
        errors.append("❌ line_items пуст или отсутствует")
    else:
        print(f"   📊 Найдено строк: {len(line_items)}")

        # Проверяем первую строку
        first_item = line_items[0]

        # Проверяем что "no" заполнен
        if 'no' in first_item:
            no_value = first_item['no']
            if not no_value or (isinstance(no_value, str) and no_value.strip() == ""):
                errors.append(f"❌ Поле 'no' пустое в первой строке: {no_value}")
            else:
                print(f"   ✅ Поле 'no' заполнено: '{no_value}'")
        else:
            errors.append("❌ Поле 'no' отсутствует в первой строке")

        # Проверяем форматирование чисел (критично для фронтенда)
        numeric_fields = ['ukt_zed', 'price_without_vat', 'amount_without_vat', 'unit_price_without_vat', 
                         'price_excluding_vat', 'amount_excluding_vat', 'unit_price_excluding_vat']
        for field in numeric_fields:
            if field in first_item:
                value = first_item[field]

                # Если это число (float), проверяем что оно не потеряло точность
                if isinstance(value, (int, float)):
                    # Конвертируем в строку для проверки
                    if isinstance(value, float):
                        # Проверяем что не потеряны десятичные знаки (критично: 4341.66 не должно стать 4341.6)
                        str_value = f"{value:.10f}".rstrip('0').rstrip('.')
                        if '.' in str_value:
                            decimals = len(str_value.split('.')[1])
                            # Если число не целое, должно быть хотя бы 2 знака после запятой
                            if decimals < 2 and value != int(value):
                                errors.append(f"❌ {field} потеряло десятичные знаки: {value} (должно быть минимум 2 знака)")
                    
                    # Проверяем длину для кодов УКТ ЗЕД (должен быть 10 цифр)
                    if field == 'ukt_zed':
                        ukt_str = str(int(value)) if isinstance(value, float) else str(value)
                        if len(ukt_str) < 10:
                            errors.append(f"❌ {field} обрезан: {value} (длина: {len(ukt_str)}, должна быть 10)")
                        elif len(ukt_str) > 10:
                            warnings.append(f"⚠️  {field} длиннее обычного: {value} (длина: {len(ukt_str)})")
                elif isinstance(value, str):
                    # Если строка, проверяем что она не обрезана
                    clean_value = value.replace(' ', '').replace(',', '').replace('.', '')
                    if field == 'ukt_zed' and len(clean_value) < 10:
                        errors.append(f"❌ {field} обрезан (строка): '{value}' (чистых цифр: {len(clean_value)})")

    # Проверяем что длинный текст присутствует
    text_fields = ['product', 'product_name', 'item', 'item_description']
    for field in text_fields:
        if field in first_item:
            value = first_item[field]
            if isinstance(value, str) and len(value) > 30:
                print(f"   ✅ Длинный текст в '{field}': {len(value)} символов")
                break

    if warnings:
        print(f"\n   ⚠️  Предупреждения ({len(warnings)}):")
        for warning in warnings:
            print(f"      {warning}")

    return errors


def test_frontend_data_parsing():
    """Тест структуры данных после парсинга"""

    if not TEST_DOCUMENT.exists():
        pytest.skip(f"Test document not found: {TEST_DOCUMENT}")

    # Получаем токен
    try:
        token = get_auth_token()
    except FileNotFoundError:
        pytest.skip("Auth token not found. Please login first.")

    # Парсим документ через API
    print(f"\n📄 Парсинг документа: {TEST_DOCUMENT.name}")
    parse_result = parse_document_via_api(TEST_DOCUMENT, token)

    if not parse_result.get('success'):
        pytest.fail(f"Парсинг не удался: {parse_result.get('error')}")

    document_id = parse_result.get('document_id')
    if not document_id:
        pytest.fail("Document ID не получен из ответа API")

    print(f"✅ Парсинг успешен. Document ID: {document_id}")

    # Сохраняем результат парсинга
    temp_dir = Path(tempfile.mkdtemp(prefix="frontend_data_test_"))
    (temp_dir / "parse_result.json").write_text(
        json.dumps(parse_result, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    # Получаем данные документа
    print(f"\n📥 Получение данных документа {document_id}...")
    doc_data = get_document_data(document_id, token)

    # Сохраняем данные документа
    (temp_dir / "document_data.json").write_text(
        json.dumps(doc_data, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    # Анализируем структуру
    print("\n🔍 Анализ структуры данных...")
    errors = analyze_data_structure(doc_data)

    if errors:
        print("\n❌ НАЙДЕНЫ ОШИБКИ:")
        for error in errors:
            print(f"  {error}")

        error_report = {
            'document_id': document_id,
            'errors': errors,
            'timestamp': __import__('time').strftime('%Y-%m-%d %H:%M:%S')
        }
        (temp_dir / "error_report.json").write_text(
            json.dumps(error_report, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )

        print(f"\n📁 Результаты сохранены в: {temp_dir}")
        pytest.fail(f"Найдено {len(errors)} ошибок. См. {temp_dir}")
    else:
        print("\n✅ Ошибок в структуре данных не найдено!")
        print(f"\n📁 Результаты сохранены в: {temp_dir}")
        print(f"   Удалите после анализа: rm -rf {temp_dir}")

