# Установка полного кода

Все Python файлы с полным кодом находятся в предыдущих сообщениях этого чата.

Для быстрой установки:

1. Скопируйте код каждого файла из chat-истории
2. Или используйте этот минимальный набор для начала работы
3. Или напишите Claude: "создай файл X" - и он создаст нужный файл

## Список файлов для копирования из чата:

### Core модули:
- src/invoiceparser/core/config.py
- src/invoiceparser/core/models.py (уже создан)
- src/invoiceparser/core/errors.py (уже создан)

### Infrastructure:
- src/invoiceparser/infra/logging_setup.py

### Preprocessing:
- src/invoiceparser/preprocessing/image_preprocessor.py
- src/invoiceparser/preprocessing/pdf_preprocessor.py

### Services:
- src/invoiceparser/services/orchestrator.py
- src/invoiceparser/services/gemini_client.py
- src/invoiceparser/services/test_engine.py

### Exporters:
- src/invoiceparser/exporters/json_exporter.py
- src/invoiceparser/exporters/excel_exporter.py

### Adapters:
- src/invoiceparser/adapters/cli_app.py
- src/invoiceparser/adapters/telegram_bot.py
- src/invoiceparser/adapters/web_api.py
- src/invoiceparser/adapters/email_poller.py

### App:
- src/invoiceparser/app/main_cli.py
- src/invoiceparser/app/main_web.py
- src/invoiceparser/app/main_telegram.py
- src/invoiceparser/app/main_email.py

### Utils:
- src/invoiceparser/utils/file_ops.py
- src/invoiceparser/utils/json_compare.py

### Tests:
- tests/conftest.py
- tests/test_image_preprocessor.py
- tests/test_pdf_preprocessor.py
- tests/test_test_engine.py
- tests/test_orchestrator.py

Все файлы присутствуют в сообщениях выше с пометкой:
# file: путь/к/файлу.py
