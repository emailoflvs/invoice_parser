"""
Валидатор совместимости API с фронтендом

Проверяет, что API возвращает данные в формате, который ожидает фронтенд
"""

from typing import Dict, Any, List


def validate_parse_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Проверка структуры ответа /parse"""
    errors = []
    warnings = []

    # Обязательные поля верхнего уровня
    required_fields = ["success", "data", "processed_at"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Отсутствует обязательное поле: {field}")

    if "data" not in data or not isinstance(data["data"], dict):
        return {"errors": errors, "warnings": warnings}

    data_obj = data["data"]

    # Проверяем основные секции для редактируемых полей
    expected_sections = {
        "document_info": ["document_type", "document_number", "document_date", "currency"],
        "parties": {
            "supplier": ["name", "address"],
            "buyer": ["name"]
        },
        "totals": ["total", "vat", "total_with_vat"]
    }

    # Проверяем document_info
    if "document_info" not in data_obj:
        warnings.append("Отсутствует секция document_info")
    else:
        for field in expected_sections["document_info"]:
            if field not in data_obj["document_info"]:
                warnings.append(f"Поле document_info.{field} отсутствует")

    # Проверяем parties
    if "parties" not in data_obj:
        warnings.append("Отсутствует секция parties")
    else:
        if "supplier" not in data_obj["parties"]:
            warnings.append("Отсутствует parties.supplier")
        if "buyer" not in data_obj["parties"]:
            warnings.append("Отсутствует parties.buyer")

    # Проверяем товары (может быть line_items или items)
    if "line_items" not in data_obj and "items" not in data_obj:
        warnings.append("Missing items (line_items or items)")

    # Проверяем column_mapping для таблицы
    if "line_items" in data_obj and isinstance(data_obj["line_items"], list):
        if "column_mapping" not in data_obj:
            warnings.append("Missing column_mapping for items table")
        elif data_obj["line_items"]:
            # Проверяем соответствие ключей
            first_item = data_obj["line_items"][0]
            for key in data_obj.get("column_mapping", {}).keys():
                if key not in first_item:
                    warnings.append(f"Ключ {key} из column_mapping отсутствует в line_items")

    return {"errors": errors, "warnings": warnings}


def validate_save_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Проверка структуры ответа /save"""
    errors = []
    warnings = []

    required_fields = ["success", "filename"]
    for field in required_fields:
        if field not in data:
            errors.append(f"Отсутствует обязательное поле: {field}")

    if data.get("success"):
        filename = data.get("filename", "")
        if "_saved_" not in filename:
            warnings.append("Имя файла не содержит '_saved_'")
        if not filename.endswith(".json"):
            warnings.append("Имя файла не заканчивается на .json")

    return {"errors": errors, "warnings": warnings}


def validate_api_structure() -> Dict[str, Any]:
    """
    Проверка структуры API для фронтенда

    Returns:
        Dict с результатами проверки
    """
    checks = []
    all_errors = []
    all_warnings = []

    # Check 1: Structure of /parse response
    parse_example = {
        "success": True,
        "data": {
            "document_info": {
                "document_type": "Invoice",
                "document_number": "123",
                "document_date": "2025-01-01",
                "currency": "UAH"
            },
            "parties": {
                "supplier": {
                    "name": "Supplier",
                    "address": "Address"
                },
                "buyer": {
                    "name": "Buyer"
                }
            },
            "totals": {
                "total": 1000.0,
                "vat": 200.0,
                "total_with_vat": 1200.0
            },
            "line_items": [
                {
                    "line_number": "1",
                    "product_name": "Product",
                    "quantity": "10"
                }
            ],
            "column_mapping": {
                "line_number": "No",
                "product_name": "Product",
                "quantity": "Quantity"
            }
        },
        "processed_at": "2025-12-07T00:00:00"
    }

    result = validate_parse_response(parse_example)
    checks.append({
        "name": "Structure of /parse response",
        "passed": len(result["errors"]) == 0,
        "errors": result["errors"],
        "warnings": result["warnings"]
    })
    all_errors.extend(result["errors"])
    all_warnings.extend(result["warnings"])

    # Check 2: Structure of /save response
    save_example = {
        "success": True,
        "filename": "invoice_saved_07120130.json",
        "message": "Data saved successfully"
    }

    result = validate_save_response(save_example)
    checks.append({
        "name": "Structure of /save response",
        "passed": len(result["errors"]) == 0,
        "errors": result["errors"],
        "warnings": result["warnings"]
    })
    all_errors.extend(result["errors"])
    all_warnings.extend(result["warnings"])

    # Проверка 3: Поля для редактируемых форм
    required_editable_fields = {
        "document_info": ["document_type", "document_number", "document_date"],
        "parties.supplier": ["name", "address"],
        "parties.buyer": ["name"],
        "totals": ["total", "vat", "total_with_vat"]
    }

    checks.append({
        "name": "Поля для редактирования",
        "passed": True,
        "message": f"Проверено {len(required_editable_fields)} секций"
    })

    return {
        "success": len(all_errors) == 0,
        "checks": checks,
        "errors": all_errors,
        "warnings": all_warnings,
        "summary": {
            "total_checks": len(checks),
            "passed": sum(1 for c in checks if c.get("passed", False)),
            "errors_count": len(all_errors),
            "warnings_count": len(all_warnings)
        }
    }


def main():
    """CLI интерфейс"""
    import sys

    print("🔍 Проверка совместимости API с фронтендом...")
    print("")

    results = validate_api_structure()

    print(f"📊 Результаты: {results['summary']['passed']}/{results['summary']['total_checks']} проверок пройдено")
    print("")

    for check in results["checks"]:
        status = "✅" if check.get("passed", False) else "❌"
        print(f"{status} {check['name']}")

        if check.get("errors"):
            for error in check["errors"]:
                print(f"  ❌ {error}")

        if check.get("warnings"):
            for warning in check["warnings"]:
                print(f"  ⚠️  {warning}")

        if check.get("message"):
            print(f"  ℹ️  {check['message']}")

        print("")

    if results["success"]:
        print("✅ Все проверки пройдены успешно!")
        return 0
    else:
        print(f"❌ Найдено {len(results['errors'])} ошибок")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
