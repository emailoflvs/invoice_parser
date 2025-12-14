#!/usr/bin/env python3
"""
Скрипт для очистки .env файла от дублирующихся переменных БД
Удаляет неиспользуемые DB_USER, DB_PASSWORD, DB_NAME
"""
import re
from pathlib import Path


def cleanup_env_file(env_path: Path):
    """Очистка .env файла от дублирующихся переменных"""
    if not env_path.exists():
        print(f"❌ Файл {env_path} не найден")
        return False

    with open(env_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Удаляем старые POSTGRES_* переменные (заменены на DB_*)
    cleaned_lines = []
    removed_vars = []

    for line in lines:
        stripped = line.strip()
        # Пропускаем пустые строки и комментарии
        if not stripped or stripped.startswith('#'):
            cleaned_lines.append(line)
            continue

        # Проверяем, не является ли это старой POSTGRES_* переменной
        if re.match(r'^POSTGRES_USER\s*=', stripped, re.IGNORECASE):
            removed_vars.append('POSTGRES_USER')
            continue
        elif re.match(r'^POSTGRES_PASSWORD\s*=', stripped, re.IGNORECASE):
            removed_vars.append('POSTGRES_PASSWORD')
            continue
        elif re.match(r'^POSTGRES_DB\s*=', stripped, re.IGNORECASE):
            removed_vars.append('POSTGRES_DB')
            continue
        elif re.match(r'^POSTGRES_PORT\s*=', stripped, re.IGNORECASE):
            removed_vars.append('POSTGRES_PORT')
            continue
        else:
            cleaned_lines.append(line)

    if removed_vars:
        # Записываем очищенный файл
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(cleaned_lines)

        print(f"✅ Удалены дублирующиеся переменные: {', '.join(removed_vars)}")
        print(f"📝 Файл {env_path} обновлен")
        return True
    else:
        print("✅ Дублирующиеся переменные не найдены")
        return False


if __name__ == "__main__":
    # В Docker контейнере .env находится в /app/.env
    if Path('/app/.env').exists():
        env_path = Path('/app/.env')
    else:
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / '.env'

    print("🧹 Очистка .env файла от дублирующихся переменных БД...")
    print()

    cleanup_env_file(env_path)

    print()
    print("📋 Используемые переменные БД:")
    print("   - DB_USER (для Docker Compose)")
    print("   - DB_PASSWORD (для Docker Compose)")
    print("   - DB_NAME (для Docker Compose)")
    print("   - DB_PORT (для Docker Compose)")
    print("   - DATABASE_URL (автоматически формируется из DB_*)")
    print()
    print("✅ Очистка завершена")

