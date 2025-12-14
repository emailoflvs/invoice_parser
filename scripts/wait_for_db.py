#!/usr/bin/env python3
"""
Wait for database to be ready
"""
import sys
import time
from pathlib import Path

# В Docker контейнере src находится в /app/src
if Path('/app/src').exists():
    sys.path.insert(0, '/app/src')
else:
    # Локально (для разработки)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoiceparser.database import init_db, get_session
from invoiceparser.core.config import Config
from sqlalchemy import text
import asyncio


async def check_db():
    """Check if database is ready"""
    try:
        config = Config.load()
        init_db(config.database_url, echo=False, pool_size=5, max_overflow=10)
        async for session in get_session():
            await session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        return False


def main():
    """Wait for database to be ready"""
    max_attempts = 30
    for i in range(max_attempts):
        if asyncio.run(check_db()):
            print("✅ Database is ready!")
            sys.exit(0)
        print(f"⏳ Waiting for database... ({i+1}/{max_attempts})")
        time.sleep(2)

    print("❌ Database is not ready after 60 seconds")
    sys.exit(1)


if __name__ == "__main__":
    main()

