#!/usr/bin/env python3
"""
Автоматический запуск визуального теста фронтенда
Парсит документ, открывает в браузере, анализирует ошибки
"""
import sys
import subprocess
from pathlib import Path

# Добавляем корень проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    print("=" * 60)
    print("🧪 АВТОМАТИЧЕСКИЙ ВИЗУАЛЬНЫЙ ТЕСТ ФРОНТЕНДА")
    print("=" * 60)
    print()

    # Проверяем что сервер запущен
    import httpx
    try:
        response = httpx.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Сервер запущен")
        else:
            print("⚠️  Сервер отвечает, но статус не 200")
    except Exception as e:
        print(f"❌ Сервер не запущен: {e}")
        print("   Запустите: python -m uvicorn src.invoiceparser.adapters.web_api:app --reload --host 0.0.0.0 --port 8000")
        return 1

    # Проверяем токен
    token_file = Path("/tmp/test_token.txt")
    if not token_file.exists():
        print("\n⚠️  Токен не найден. Нужен логин.")
        username = input("Username: ")
        password = input("Password: ")

        import json
        response = httpx.post(
            "http://localhost:8000/login",
            data={"username": username, "password": password}
        )

        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                token_file.write_text(token)
                print("✅ Токен сохранен")
            else:
                print("❌ Токен не получен")
                return 1
        else:
            print(f"❌ Ошибка логина: {response.status_code}")
            return 1

    # Запускаем тест
    print("\n🚀 Запуск теста...")
    print("-" * 60)

    result = subprocess.run(
        ["pytest", "tests/test_frontend_visual.py", "-v", "-s"],
        cwd=project_root
    )

    print("-" * 60)

    if result.returncode == 0:
        print("\n✅ Тест пройден успешно!")
        return 0
    else:
        print("\n❌ Тест выявил ошибки. Проверьте вывод выше.")
        return result.returncode

if __name__ == "__main__":
    sys.exit(main())

