#!/usr/bin/env python3
"""Генерация детального отчета по тестам v8, v9, v10"""
import json
from pathlib import Path
from datetime import datetime

files = [
    "output/dnipromash_gemini-2.5-pro_12061959_8errors.json",
    "output/dnipromash_gemini-2.5-pro_12062003_8errors.json",
    "output/dnipromash_gemini-2.5-pro_12062006_8errors.json"
]

print("# Детальные результаты тестирования v8, v9, v10")
print("## Модель: gemini-2.5-pro")
print("## Эталон: gemini_thinking_2_prompts_v7/dnipromash_gemini_thinking_2_prompts_v7.json")
print("")

for filepath in files:
    file = Path(filepath)
    if not file.exists():
        continue

    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    prompt = data.get("prompt", "")
    model = data.get("model", "")

    print(f"## {prompt} ({model})")
    print("")

    for test in data.get("tests", []):
        test_num = test.get("test_num", 0)
        errors = test.get("errors", 0)
        timestamp = test.get("timestamp", "")

        # Парсим время
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = dt.strftime("%H:%M:%S")
        except:
            time_str = timestamp.split('T')[1].split('.')[0] if 'T' in timestamp else ""

        print(f"### ПАРСИНГ {test_num}: {time_str} ({errors} ошибки)")
        print("")
        print("| № | Раздел | Поле | Ожидается | Получено |")
        print("|---|--------|------|-----------|----------|")

        all_differences = test.get("test_results", {}).get("all_differences", [])
        for diff in all_differences:
            line = diff.get("line", "header")
            path = diff.get("path", diff.get("field", ""))
            expected = str(diff.get("expected", ""))
            actual = str(diff.get("actual", ""))
            print(f"| {line} | {path} | {expected} | {actual} |")

        print("")
        print("---")
        print("")

