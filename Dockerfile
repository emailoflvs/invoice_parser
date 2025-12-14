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

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ /app/src/
COPY prompts/ /app/prompts/
COPY static/ /app/static/
COPY scripts/ /app/scripts/
COPY alembic.ini /app/alembic.ini
COPY alembic/ /app/alembic/

# Создаём необходимые директории
RUN mkdir -p /app/invoices /app/output /app/temp /app/logs /app/examples

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app/src
ENV LOGS_DIR=/app/logs
ENV OUTPUT_DIR=/app/output
ENV TEMP_DIR=/app/temp
ENV INVOICES_DIR=/app/invoices
ENV EXAMPLES_DIR=/app/examples
ENV PROMPTS_DIR=/app/prompts

# Expose порт для веб-интерфейса
EXPOSE 8000

# По умолчанию запускаем веб-интерфейс
CMD ["python", "-m", "invoiceparser.app.main_web"]
