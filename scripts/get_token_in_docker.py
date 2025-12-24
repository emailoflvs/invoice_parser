#!/usr/bin/env python3
"""Получение токена внутри Docker контейнера"""
import sys
import json
import httpx

def get_token():
    """Получить токен через регистрацию/логин"""
    import time
    test_user = f"test_user_{int(time.time())}"
    test_pass = "test_pass_123"

    try:
        # Пробуем зарегистрироваться
        with httpx.Client(timeout=10.0) as client:
            try:
                response = client.post(
                    "http://localhost:8000/api/auth/register",
                    json={"username": test_user, "password": test_pass}
                )
                # Игнорируем ошибки регистрации
            except:
                pass

            # Логинимся
            time.sleep(0.5)
            response = client.post(
                "http://localhost:8000/api/auth/login",
                json={"username": test_user, "password": test_pass}
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("access_token", "")
            if token:
                print(token)
                return 0
            else:
                print("NO_TOKEN", file=sys.stderr)
                return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(get_token())

