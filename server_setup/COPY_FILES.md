# Копирование файлов на сервер через SSH

Есть несколько способов скопировать файлы на сервер через SSH.

## Способ 1: SCP (Simple Copy) - Рекомендуется

### Копирование одного файла:
```bash
scp /путь/к/локальному/файлу debian@57.129.62.58:/opt/docker-projects/invoice_parser/файл
```

### Примеры:
```bash
# Копирование .env файла
scp .env debian@57.129.62.58:/opt/docker-projects/invoice_parser/.env

# Копирование credentials
scp google_sheets_credentials.json debian@57.129.62.58:/opt/docker-projects/invoice_parser/

# Копирование директории (рекурсивно)
scp -r ./some_directory debian@57.129.62.58:/opt/docker-projects/invoice_parser/
```

### Использование готового скрипта:
```bash
cd /home/lvs/Desktop/AI/servers/invoice_parser/server_setup
chmod +x copy_files_ssh.sh
./copy_files_ssh.sh .env google_sheets_credentials.json
```

## Способ 2: RSYNC - Для синхронизации

RSYNC более эффективен для больших файлов и директорий, показывает прогресс:

```bash
# Синхронизация одного файла
rsync -avz --progress .env debian@57.129.62.58:/opt/docker-projects/invoice_parser/

# Синхронизация директории
rsync -avz --progress ./some_dir/ debian@57.129.62.58:/opt/docker-projects/invoice_parser/some_dir/

# Исключение определенных файлов
rsync -avz --progress --exclude '*.pyc' --exclude '__pycache__' \
  ./src/ debian@57.129.62.58:/opt/docker-projects/invoice_parser/src/
```

## Способ 3: Через SSH с tar (для множества файлов)

Полезно для копирования нескольких файлов одновременно:

```bash
# Создание архива и передача через SSH
tar czf - файл1 файл2 директория | ssh debian@57.129.62.58 "cd /opt/docker-projects/invoice_parser && tar xzf -"
```

## Способ 4: Python скрипт (автоматизация)

Используйте готовый скрипт `deploy_via_git.py`, который автоматически копирует файлы.

Чтобы добавить новые файлы в список копирования, отредактируйте скрипт:

```python
# В файле server_setup/deploy_via_git.py найдите:
additional_files = [
    '.env',
    'google_sheets_credentials.json',
    # Добавьте сюда свои файлы:
    # 'config.json',
    # 'secrets.yaml',
]
```

## Способ 5: Прямое редактирование через SSH

Для небольших файлов можно создать/отредактировать прямо на сервере:

```bash
ssh debian@57.129.62.58
cd /opt/docker-projects/invoice_parser
nano .env  # или vim, или другой редактор
```

## Примеры для проекта invoice_parser

### Копирование конфигурационных файлов:
```bash
# Из локальной директории проекта
cd /home/lvs/Desktop/AI/servers/invoice_parser

# .env файл
scp .env debian@57.129.62.58:/opt/docker-projects/invoice_parser/.env

# Google Sheets credentials
scp google_sheets_credentials.json debian@57.129.62.58:/opt/docker-projects/invoice_parser/

# Если нужно скопировать несколько файлов
scp .env google_sheets_credentials.json debian@57.129.62.58:/opt/docker-projects/invoice_parser/
```

### Копирование директорий с данными (если нужно):
```bash
# Копирование директории invoices (если есть локальные данные)
rsync -avz --progress ./invoices/ debian@57.129.62.58:/opt/docker-projects/invoice_parser/invoices/

# Копирование директории prompts (если есть изменения)
rsync -avz --progress ./prompts/ debian@57.129.62.58:/opt/docker-projects/invoice_parser/prompts/
```

## Автоматизация через скрипт

Создан скрипт `copy_files_ssh.sh` для удобного копирования:

```bash
# Копирование стандартных файлов
./copy_files_ssh.sh

# Копирование конкретных файлов
./copy_files_ssh.sh .env config.json secrets.yaml
```

## Проверка скопированных файлов

После копирования проверьте на сервере:

```bash
ssh debian@57.129.62.58
cd /opt/docker-projects/invoice_parser
ls -la .env google_sheets_credentials.json
```

## Безопасность

⚠️ **Важно**: Не копируйте файлы с секретами через незащищенные каналы. Используйте SSH (SCP/RSYNC используют SSH по умолчанию).

Для файлов с паролями и ключами:
- Используйте переменные окружения вместо файлов где возможно
- Храните секреты в `.env` файлах (которые в `.gitignore`)
- Используйте менеджеры секретов для production









