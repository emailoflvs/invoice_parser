# Tests Directory

Все скрипты для тестирования парсера находятся здесь.

## Структура

```
tests/
├── README.md                    # Этот файл
├── test_v8.py                  # Тест промптов v8 на 3 файлах
├── test_v9.py                  # Тест промпта items_v9.txt на dnipromash
├── test_all_items_prompts.py   # Тест всех items промптов
├── batch_process.py            # Батч-обработка всех файлов из INVOICES_DIR
├── batch_compare.py            # Сравнение результатов батч-обработки
├── compare_v8.py               # Сравнение результатов v8 с эталонами
├── run_v8.sh                   # Запуск теста v8
├── run_v9_test.sh              # Запуск теста v9
└── run_batch.sh                # Запуск батч-обработки
```

## Быстрый старт

### Тест v9 на dnipromash (сравнение с эталоном v7)
```bash
./tests/run_v9_test.sh
```

### Тест v8 на 3 файлах
```bash
./tests/run_v8.sh
```

### Батч-обработка всех файлов
```bash
./tests/run_batch.sh
```

### Сравнение результатов
```bash
docker-compose exec -T app python /app/tests/compare_v8.py
```

## Пути

Все скрипты автоматически определяют корневую директорию проекта и используют правильные пути:
- `../prompts/` - промпты
- `../invoices/` - входные файлы
- `../output/` - результаты
- `../examples/` - эталоны для сравнения

## Запуск напрямую через Docker

```bash
# Тест v9
docker-compose exec -T app python /app/tests/test_v9.py

# Тест v8
docker-compose exec -T app python /app/tests/test_v8.py

# Батч-обработка
docker-compose exec -T app python /app/tests/batch_process.py
```
