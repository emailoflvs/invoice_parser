#!/usr/bin/env python3
"""
Дебаг скрипт: Показує як Claude бачить структуру першого товару в PDF
"""

import anthropic
import os
import base64

def debug_first_item():
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY не установлен")

    client = anthropic.Anthropic(api_key=api_key)

    # Читаем PDF
    with open('invoiceDneprSpecMash.pdf', 'rb') as f:
        pdf_data = f.read()

    system_prompt = """Ты OCR-аналитик PDF документов.

КРИТИЧЕСКИ ВАЖНО:
В PDF-таблицах значения часто переносятся на несколько строк внутри одной ячейки.
Например, артикул может выглядеть так:
┌─────────────────┐
│521.318.01.04.06.│
│00               │
│1                │
└─────────────────┘

Это ОДНА ячейка с тремя строками: "521.318.01.04.06.00\n1"

Задание:
1. Найди первую строку таблицы товаров (позиция №1)
2. Найди ячейку "Артикул" или "УКТ ЗЕД" или код товара
3. Покажи ВСЁ содержимое этой ячейки построчно
4. Обрати внимание: если под основным артикулом есть дополнительные цифры - это тоже часть ячейки!

Формат ответа:
```
Первый товар (позиция №1):

Ячейка "Артикул/УКТ ЗЕД" (построчно):
├─ Строка 1: [точный текст]
├─ Строка 2: [точный текст или "нет"]
└─ Строка 3: [точный текст или "нет"]

Есть ли под артикулом дополнительные символы/цифры? [да/нет]
Если да - какие: [текст]
```

Будь максимально внимателен к переносам строк."""

    print("Отправка запроса к Claude...")

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64.standard_b64encode(pdf_data).decode('utf-8')
                        }
                    },
                    {
                        "type": "text",
                        "text": "Проанализируй первый товар в таблице. Покажи структуру ячеек."
                    }
                ]
            }
        ],
        timeout=120.0
    )

    print(message.content[0].text)

if __name__ == "__main__":
    debug_first_item()
