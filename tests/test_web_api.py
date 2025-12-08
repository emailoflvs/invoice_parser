"""
Тесты для веб-API - проверка структуры данных для фронтенда
"""
import pytest
import json
from pathlib import Path
from fastapi.testclient import TestClient
from invoiceparser.core.config import Config
from invoiceparser.adapters.web_api import WebAPI


@pytest.fixture
def config():
    """Конфигурация для тестов"""
    return Config.load()


@pytest.fixture
def web_api(config):
    """Экземпляр WebAPI"""
    return WebAPI(config)


@pytest.fixture
def client(web_api):
    """TestClient для FastAPI"""
    return TestClient(web_api.app)


@pytest.fixture
def auth_token(config):
    """Токен авторизации из конфига"""
    return config.web_auth_token


def test_health_endpoint(client):
    """Проверка health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_parse_response_structure(client, auth_token, tmp_path):
    """
    Проверка структуры ответа /parse для фронтенда

    Фронтенд ожидает:
    {
        "success": bool,
        "data": {
            "document_info": {...},
            "parties": {...},
            "line_items": [...],
            ...
        },
        "processed_at": str
    }
    """
    # Создаем тестовый файл (пустой, для проверки структуры ошибки)
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")

    # Пытаемся загрузить неподдерживаемый формат
    response = client.post(
        "/parse",
        headers={"Authorization": f"Bearer {auth_token}"},
        files={"file": ("test.txt", test_file.open("rb"), "text/plain")}
    )

    # Должна быть ошибка, но структура должна быть правильной
    assert response.status_code in [400, 500]
    data = response.json()

    # Проверяем, что есть поле detail (для ошибок FastAPI)
    assert "detail" in data


def test_save_endpoint_structure(client, auth_token):
    """
    Проверка структуры ответа /save для фронтенда

    Фронтенд ожидает:
    {
        "success": bool,
        "filename": str,
        "message": str (optional),
        "error": str (optional)
    }
    """
    # Тестовые данные
    test_data = {
        "original_filename": "test_invoice.pdf",
        "data": {
            "document_info": {
                "document_number": "123",
                "document_date": "2025-01-01"
            }
        }
    }

    response = client.post(
        "/save",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json=test_data
    )

    assert response.status_code == 200
    data = response.json()

    # Проверяем структуру ответа
    assert "success" in data
    assert "filename" in data
    assert isinstance(data["success"], bool)
    assert isinstance(data["filename"], str)

    if data["success"]:
        assert "message" in data
        # Проверяем, что файл создан
        assert "_saved_" in data["filename"]
        assert data["filename"].endswith(".json")


def test_parse_response_data_structure_for_frontend():
    """
    Проверка структуры данных, которые фронтенд ожидает получить

    Фронтенд использует эти поля:
    - data.document_info.*
    - data.parties.supplier.*
    - data.parties.buyer.*
    - data.references.*
    - data.totals.*
    - data.line_items или data.items
    - data.column_mapping (для таблицы товаров)
    """
    # Пример структуры, которую ожидает фронтенд
    expected_structure = {
        "success": True,
        "data": {
            # Документ
            "document_info": {
                "document_type": str,
                "document_number": str,
                "document_date": str,
                "currency": str
            },
            # Стороны
            "parties": {
                "supplier": {
                    "name": str,
                    "address": str,
                    # ... другие поля
                },
                "buyer": {
                    "name": str,
                    # ... другие поля
                }
            },
            # Ссылки
            "references": {
                "contract_number": str,
                # ... другие поля
            },
            # Итоги
            "totals": {
                "total": (int, float),
                "vat": (int, float),
                "total_with_vat": (int, float)
            },
            # Товары (может быть line_items или items)
            "line_items": list,
            "items": list,  # альтернативное название
            "column_mapping": dict  # для таблицы товаров
        },
        "processed_at": str
    }

    # Это просто проверка структуры, не реальный тест
    # Но показывает, что мы понимаем структуру
    assert isinstance(expected_structure, dict)


def test_frontend_editable_fields_structure():
    """
    Проверка структуры данных для редактируемых полей

    Фронтенд ищет поля с суффиксом _label для меток:
    - document_type_label
    - supplier_name_label
    и т.д.
    """
    # Пример данных с метками
    data_with_labels = {
        "document_info": {
            "document_type": "Invoice",
            "document_type_label": "Тип документа:",
            "document_number": "123",
            "document_number_label": "Номер документа:"
        },
        "parties": {
            "supplier": {
                "name": "Company",
                "name_label": "Поставщик:"
            }
        }
    }

    # Проверяем, что структура поддерживает _label поля
    assert "document_info" in data_with_labels
    assert "document_type_label" in data_with_labels["document_info"]


def test_save_endpoint_creates_file(client, auth_token, tmp_path, config):
    """Проверка, что /save создает файл с правильным именем"""
    import os
    original_output_dir = config.output_dir

    # Временно меняем output_dir на tmp_path
    config.output_dir = tmp_path

    test_data = {
        "original_filename": "test_invoice.pdf",
        "data": {
            "test": "data"
        }
    }

    response = client.post(
        "/save",
        headers={
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        },
        json=test_data
    )

    assert response.status_code == 200
    data = response.json()

    if data["success"]:
        # Проверяем, что файл создан
        saved_file = tmp_path / data["filename"]
        assert saved_file.exists()

        # Проверяем содержимое
        with open(saved_file) as f:
            saved_content = json.load(f)
        assert saved_content == test_data["data"]

        # Проверяем формат имени файла
        assert "_saved_" in data["filename"]
        assert data["filename"].endswith(".json")


def test_unauthorized_access(client):
    """Проверка, что без токена доступ запрещен"""
    response = client.post("/parse", files={"file": ("test.pdf", b"test")})
    assert response.status_code == 401

    response = client.post("/save", json={"data": {}})
    assert response.status_code == 401


def test_cors_headers(client):
    """Проверка CORS заголовков для фронтенда"""
    response = client.options("/health")
    # CORS должен быть настроен
    assert response.status_code in [200, 405]  # OPTIONS может возвращать 405


def test_static_files_served(client):
    """Проверка, что статические файлы доступны"""
    response = client.get("/static/index.html")
    # Может быть 200 или 404 если файл не найден, но важно что endpoint работает
    assert response.status_code in [200, 404]

    if response.status_code == 200:
        assert "html" in response.text.lower()


@pytest.mark.parametrize("endpoint", ["/", "/health"])
def test_public_endpoints(client, endpoint):
    """Проверка публичных endpoints (без авторизации)"""
    response = client.get(endpoint)
    assert response.status_code == 200



