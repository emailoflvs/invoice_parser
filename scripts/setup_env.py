#!/usr/bin/env python3
"""
Automatic setup script for .env file
Configures all necessary settings including JWT_SECRET_KEY, database, etc.
"""
import os
import secrets
from pathlib import Path


def generate_jwt_secret() -> str:
    """Generate a secure JWT secret key"""
    return secrets.token_hex(64)


def read_env_file(env_path: Path) -> dict:
    """Read existing .env file and return as dict"""
    env_vars = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    # Разделяем на ключ и значение
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Убираем комментарии из значения (все после #)
                    if '#' in value:
                        value = value.split('#')[0].strip()
                    env_vars[key] = value
    return env_vars


def write_env_file(env_path: Path, env_vars: dict, comments: dict = None):
    """Write .env file with variables and comments"""
    if comments is None:
        comments = {}

    # Read existing file to preserve structure
    existing_lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            existing_lines = f.readlines()

    # Create new content
    new_lines = []
    seen_vars = set()

    # Process existing lines
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            # Keep comments and empty lines
            new_lines.append(line)
        elif '=' in stripped:
            # Извлекаем ключ (до =)
            key = stripped.split('=', 1)[0].strip()
            # Проверяем, не является ли это старыми POSTGRES_* переменными
            if key in ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'POSTGRES_PORT']:
                # Пропускаем старые переменные (будут заменены на DB_*)
                continue
            elif key in env_vars:
                # Update existing variable
                comment = comments.get(key, '')
                if comment:
                    new_lines.append(f"{key}={env_vars[key]}  # {comment}\n")
                else:
                    new_lines.append(f"{key}={env_vars[key]}\n")
                seen_vars.add(key)
            else:
                # Keep existing variable that we don't manage
                new_lines.append(line)

    # Add new variables that weren't in file
    for key, value in env_vars.items():
        if key not in seen_vars:
            comment = comments.get(key, '')
            if comment:
                new_lines.append(f"{key}={value}  # {comment}\n")
            else:
                new_lines.append(f"{key}={value}\n")

    # Write file
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


def setup_env():
    """Main setup function"""
    # Определяем путь к .env файлу
    # В Docker контейнере .env монтируется в /app/.env
    # Локально может быть в корне проекта
    if Path('/app/.env').exists():
        env_path = Path('/app/.env')  # Docker контейнер
    else:
        project_root = Path(__file__).resolve().parent.parent
        env_path = project_root / '.env'  # Локально

    print("🔧 Setting up .env file...")
    print()

    # Read existing env
    existing_env = read_env_file(env_path)

    # Default values
    env_vars = {}
    comments = {}

    # Database settings (для Docker Compose)
    # Проверяем старые POSTGRES_* переменные для миграции
    if 'POSTGRES_USER' in existing_env and 'DB_USER' not in existing_env:
        env_vars['DB_USER'] = existing_env.get('POSTGRES_USER', 'invoiceparser')
    else:
        env_vars['DB_USER'] = existing_env.get('DB_USER', 'invoiceparser')
    comments['DB_USER'] = 'PostgreSQL username (для Docker Compose)'

    if 'POSTGRES_PASSWORD' in existing_env and 'DB_PASSWORD' not in existing_env:
        env_vars['DB_PASSWORD'] = existing_env.get('POSTGRES_PASSWORD', 'invoiceparser_password')
    else:
        env_vars['DB_PASSWORD'] = existing_env.get('DB_PASSWORD', 'invoiceparser_password')
    comments['DB_PASSWORD'] = 'PostgreSQL password (для Docker Compose)'

    if 'POSTGRES_DB' in existing_env and 'DB_NAME' not in existing_env:
        env_vars['DB_NAME'] = existing_env.get('POSTGRES_DB', 'invoiceparser')
    else:
        env_vars['DB_NAME'] = existing_env.get('DB_NAME', 'invoiceparser')
    comments['DB_NAME'] = 'PostgreSQL database name (для Docker Compose)'

    if 'POSTGRES_PORT' in existing_env and 'DB_PORT' not in existing_env:
        env_vars['DB_PORT'] = existing_env.get('POSTGRES_PORT', '5432')
    else:
        env_vars['DB_PORT'] = existing_env.get('DB_PORT', '5432')
    comments['DB_PORT'] = 'PostgreSQL port (для Docker Compose)'

    # Database URL (автоматически формируется из DB_* переменных)
    db_user = env_vars['DB_USER']
    db_password = env_vars['DB_PASSWORD']
    db_name = env_vars['DB_NAME']
    db_host = 'db'  # Имя сервиса в docker-compose
    db_port = '5432'  # Внутренний порт в Docker сети
    env_vars['DATABASE_URL'] = f'postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
    comments['DATABASE_URL'] = 'Database connection URL (автоматически формируется из DB_*)'

    # JWT Settings
    if 'JWT_SECRET_KEY' not in existing_env or existing_env.get('JWT_SECRET_KEY') == 'your-secret-key-change-in-production-use-long-random-string':
        env_vars['JWT_SECRET_KEY'] = generate_jwt_secret()
        print("✅ Generated new JWT_SECRET_KEY")
    else:
        env_vars['JWT_SECRET_KEY'] = existing_env['JWT_SECRET_KEY']
        print("✅ Using existing JWT_SECRET_KEY")
    comments['JWT_SECRET_KEY'] = 'JWT secret key for token signing (auto-generated)'

    env_vars['JWT_ALGORITHM'] = existing_env.get('JWT_ALGORITHM', 'HS256')
    comments['JWT_ALGORITHM'] = 'JWT algorithm'

    env_vars['JWT_ACCESS_TOKEN_EXPIRE_MINUTES'] = existing_env.get('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '43200')
    comments['JWT_ACCESS_TOKEN_EXPIRE_MINUTES'] = 'JWT token expiration time in minutes (43200 = 30 days)'

    # Application settings
    env_vars['MODE'] = existing_env.get('MODE', 'NORMAL')
    comments['MODE'] = 'Application mode: NORMAL or TEST'

    env_vars['LOG_LEVEL'] = existing_env.get('LOG_LEVEL', 'INFO')
    comments['LOG_LEVEL'] = 'Logging level: DEBUG, INFO, WARNING, ERROR'

    env_vars['DEV_MODE'] = existing_env.get('DEV_MODE', 'false')
    comments['DEV_MODE'] = 'Development mode (auto-reload)'

    # Database settings
    env_vars['DB_ECHO'] = existing_env.get('DB_ECHO', 'false')
    comments['DB_ECHO'] = 'SQLAlchemy query logging'

    env_vars['DB_POOL_SIZE'] = existing_env.get('DB_POOL_SIZE', '50')
    comments['DB_POOL_SIZE'] = 'Database connection pool size'

    env_vars['DB_MAX_OVERFLOW'] = existing_env.get('DB_MAX_OVERFLOW', '20')
    comments['DB_MAX_OVERFLOW'] = 'Database max overflow connections'

    env_vars['DB_AUTO_MIGRATE'] = existing_env.get('DB_AUTO_MIGRATE', 'true')
    comments['DB_AUTO_MIGRATE'] = 'Auto-run migrations on startup'

    # Web API settings
    env_vars['WEB_HOST'] = existing_env.get('WEB_HOST', '0.0.0.0')
    comments['WEB_HOST'] = 'Web server host'

    env_vars['WEB_PORT'] = existing_env.get('WEB_PORT', '8000')
    comments['WEB_PORT'] = 'Web server port'

    env_vars['MAX_FILE_SIZE_MB'] = existing_env.get('MAX_FILE_SIZE_MB', '50')
    comments['MAX_FILE_SIZE_MB'] = 'Maximum upload file size in MB'

    # Directories (relative paths)
    env_vars['INVOICES_DIR'] = existing_env.get('INVOICES_DIR', 'invoices')
    comments['INVOICES_DIR'] = 'Directory for invoice files'

    env_vars['OUTPUT_DIR'] = existing_env.get('OUTPUT_DIR', 'output')
    comments['OUTPUT_DIR'] = 'Directory for output files'

    env_vars['LOGS_DIR'] = existing_env.get('LOGS_DIR', 'logs')
    comments['LOGS_DIR'] = 'Directory for log files'

    env_vars['TEMP_DIR'] = existing_env.get('TEMP_DIR', 'temp')
    comments['TEMP_DIR'] = 'Directory for temporary files'

    env_vars['EXAMPLES_DIR'] = existing_env.get('EXAMPLES_DIR', 'examples')
    comments['EXAMPLES_DIR'] = 'Directory for example files'

    env_vars['PROMPTS_DIR'] = existing_env.get('PROMPTS_DIR', 'prompts')
    comments['PROMPTS_DIR'] = 'Directory for prompt files'

    # Keep existing important settings if they exist
    important_keys = [
        'GEMINI_API_KEY',
        'GEMINI_MODEL',
        'GEMINI_MODEL_FAST',
        'GEMINI_TIMEOUT',
        'PROMPT_HEADER_PATH',
        'PROMPT_ITEMS_PATH',
        'PROMPT_ITEMS_HEADER',
        'TELEGRAM_BOT_TOKEN',
        'TELEGRAM_ALLOWED_USER_IDS',
        # Email settings
        'EMAIL_HOST',
        'EMAIL_PORT',
        'EMAIL_USE_SSL',
        'EMAIL_LOGIN',
        'EMAIL_PASSWORD',
        'EMAIL_ALLOWED_SENDERS',
        'EMAIL_POLL_INTERVAL',
        'EMAIL_POLL_RETRY_DELAY',
        # Google Sheets
        'SHEETS_SPREADSHEET_ID',
        'SHEETS_CREDENTIALS_PATH',
        'SHEETS_HEADER_SHEET',
        'SHEETS_ITEMS_SHEET',
        'EXPORT_ONLINE_EXCEL_ENABLED',
    ]

    for key in important_keys:
        if key in existing_env:
            env_vars[key] = existing_env[key]

    # Write file
    if env_path.exists():
        print(f"📝 Updating existing .env file: {env_path}")
    else:
        print(f"📝 Creating new .env file: {env_path}")

    write_env_file(env_path, env_vars, comments)

    print()
    print("✅ .env file configured successfully!")
    print()
    print("📋 Summary:")
    print(f"   Database: {env_vars['DB_NAME']} (user: {env_vars['DB_USER']})")
    print(f"   Database URL: {env_vars['DATABASE_URL'][:50]}...")
    print(f"   JWT Secret: {'✅ Set' if env_vars.get('JWT_SECRET_KEY') else '❌ Not set'}")
    print(f"   Web Server: {env_vars['WEB_HOST']}:{env_vars['WEB_PORT']}")
    print()
    print("📝 Database configuration:")
    print("   - DB_* variables are used by Docker Compose")
    print("   - DATABASE_URL is auto-generated from DB_* variables")
    print()
    print("⚠️  IMPORTANT:")
    print("   - Check GEMINI_API_KEY is set if you need AI parsing")
    print("   - Review all settings in .env file")
    print("   - Never commit .env file to version control")


if __name__ == "__main__":
    setup_env()

