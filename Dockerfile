FROM python:3.11-slim

# Устанавливаем системные зависимости для работы с изображениями и PDF
RUN apt-get update && apt-get install -y \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем файлы зависимостей
COPY requirements.txt .
COPY pyproject.toml .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY static/ /app/static/

# Создаём необходимые директории
RUN mkdir -p /app/invoices /app/output/temp /app/logs /app/examples

# Устанавливаем PYTHONPATH
ENV PYTHONPATH=/app/src

# По умолчанию запускаем CLI
CMD ["python", "-m", "invoiceparser.app.main_cli", "--help"]
