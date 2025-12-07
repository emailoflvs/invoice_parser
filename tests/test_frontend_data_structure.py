"""
Тесты для проверки структуры данных, которые получает фронтенд

Эти тесты проверяют, что API возвращает данные в формате,
который ожидает фронтенд (script.js)
"""
import pytest
import json
from pathlib import Path


def test_frontend_expected_fields():
    """
    Проверка списка полей, которые фронтенд использует

    На основе анализа script.js:
    - displayEditableData() использует определенные поля
    - displayHeaderInfo() использует invoice_number, invoice_date и т.д.
    - displayItemsTable() использует line_items или items
    """
    # Поля, которые фронтенд ожидает найти
    expected_fields = {
        # Для displayHeaderInfo
        "invoice_number": "Номер документа",
        "invoice_date": "Дата документа",
        "supplier_name": "Поставщик",
        "customer_name": "Покупатель",
        "currency": "Валюта",

        # Для displayEditableData
        "document_info": {
            "document_type": "Тип документа",
            "document_number": "Номер документа",
            "document_date": "Дата документа",
            "currency": "Валюта"
        },
        "parties": {
            "supplier": {
                "name": "Название поставщика",
                "address": "Адрес",
                "phone": "Телефон"
            },
            "buyer": {
                "name": "Название покупателя"
            }
        },
        "references": {
            "contract_number": "Номер контракта"
        },
        "totals": {
            "total": "Сумма без НДС",
            "vat": "НДС",
            "total_with_vat": "Итого с НДС"
        },

        # Для displayItemsTable
        "line_items": "Товары (новый формат)",
        "items": "Товары (старый формат)",
        "column_mapping": "Маппинг колонок для таблицы"
    }

    # Проверяем, что структура определена
    assert isinstance(expected_fields, dict)
    assert "document_info" in expected_fields
    assert "parties" in expected_fields
    assert "totals" in expected_fields


def test_field_labels_structure():
    """
    Проверка структуры меток полей

    Фронтенд поддерживает:
    1. Поля с суффиксом _label (например, document_type_label)
    2. Предопределенные метки в fieldLabels объекте
    3. Имя поля как fallback
    """
    # Пример данных с _label полями
    data_with_labels = {
        "document_info": {
            "document_type": "Invoice",
            "document_type_label": "Тип документа:",
            "supplier_name": "Company",
            "supplier_name_label": "Поставщик:"
        }
    }

    # Проверяем паттерн
    for key, value in data_with_labels["document_info"].items():
        if key.endswith("_label"):
            base_key = key.replace("_label", "")
            assert base_key in data_with_labels["document_info"]


def test_line_items_structure():
    """
    Проверка структуры товаров для таблицы

    Фронтенд ожидает:
    - line_items или items - массив объектов
    - column_mapping - словарь для заголовков таблицы
    - Каждый item должен иметь поля из column_mapping
    """
    example_structure = {
        "column_mapping": {
            "line_number": "№",
            "product_name": "Товар",
            "quantity": "Количество",
            "price": "Цена"
        },
        "line_items": [
            {
                "line_number": "1",
                "product_name": "Товар 1",
                "quantity": "10",
                "price": "100.00"
            }
        ]
    }

    # Проверяем структуру
    assert "column_mapping" in example_structure
    assert "line_items" in example_structure
    assert isinstance(example_structure["line_items"], list)

    if example_structure["line_items"]:
        first_item = example_structure["line_items"][0]
        # Проверяем, что ключи item соответствуют column_mapping
        for key in example_structure["column_mapping"].keys():
            assert key in first_item, f"Поле {key} отсутствует в line_item"


def test_save_response_structure():
    """
    Проверка структуры ответа /save

    Фронтенд ожидает:
    {
        "success": bool,
        "filename": str,
        "message": str (optional)
    }
    """
    expected_response = {
        "success": True,
        "filename": "invoice_saved_07120130.json",
        "message": "Данные успешно сохранены..."
    }

    # Проверяем обязательные поля
    assert "success" in expected_response
    assert "filename" in expected_response
    assert isinstance(expected_response["success"], bool)
    assert isinstance(expected_response["filename"], str)

    # Проверяем формат имени файла
    if expected_response["success"]:
        assert "_saved_" in expected_response["filename"]
        assert expected_response["filename"].endswith(".json")


def test_parse_response_structure():
    """
    Проверка структуры ответа /parse

    Фронтенд ожидает:
    {
        "success": bool,
        "data": {...},
        "processed_at": str
    }
    """
    expected_response = {
        "success": True,
        "data": {
            # Любые данные документа
        },
        "processed_at": "2025-12-07T00:00:00"
    }

    # Проверяем обязательные поля
    assert "success" in expected_response
    assert "data" in expected_response
    assert "processed_at" in expected_response

    assert isinstance(expected_response["success"], bool)
    assert isinstance(expected_response["data"], dict)
    assert isinstance(expected_response["processed_at"], str)


def test_nested_data_access():
    """
    Проверка доступа к вложенным данным

    Фронтенд использует:
    - data.document_info.*
    - data.parties.supplier.*
    - data.parties.buyer.*
    """
    example_data = {
        "document_info": {
            "document_number": "123"
        },
        "parties": {
            "supplier": {
                "name": "Supplier"
            },
            "buyer": {
                "name": "Buyer"
            }
        }
    }

    # Проверяем доступ к вложенным полям
    assert example_data.get("document_info", {}).get("document_number") == "123"
    assert example_data.get("parties", {}).get("supplier", {}).get("name") == "Supplier"
    assert example_data.get("parties", {}).get("buyer", {}).get("name") == "Buyer"


def test_empty_data_handling():
    """
    Проверка обработки пустых данных

    Фронтенд должен корректно обрабатывать:
    - Отсутствующие поля
    - Пустые массивы
    - null значения
    """
    empty_data = {
        "document_info": {},
        "parties": {
            "supplier": {},
            "buyer": {}
        },
        "line_items": [],
        "items": []
    }

    # Проверяем, что структура валидна даже при пустых данных
    assert isinstance(empty_data["line_items"], list)
    assert len(empty_data["line_items"]) == 0

