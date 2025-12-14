#!/usr/bin/env python3
"""
Script to create a new user in the database.
Can be used for initial setup or creating additional users.

Использование в Docker:
    docker-compose exec app python scripts/create_user.py <username> <password> [email] [--superuser]
"""
import sys
import asyncio
from pathlib import Path

# Add src to path
# В Docker контейнере src находится в /app/src
if Path('/app/src').exists():
    sys.path.insert(0, '/app/src')
else:
    # Локально (для разработки)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from invoiceparser.core.config import Config
from invoiceparser.database import init_db, get_session
from invoiceparser.database.models import User
from invoiceparser.auth import get_password_hash, get_user_by_username
from sqlalchemy import select


async def create_user(username: str, password: str, email: str = None, is_superuser: bool = False):
    """
    Create a new user in the database

    Args:
        username: Username
        password: Plain text password
        email: Email address (optional)
        is_superuser: Whether user should have superuser privileges
    """
    config = Config.load()

    # Initialize database
    init_db(
        database_url=config.database_url,
        echo=config.db_echo,
        pool_size=config.db_pool_size,
        max_overflow=config.db_max_overflow
    )

    async for session in get_session():
        # Check if user already exists
        existing_user = await get_user_by_username(session, username)
        if existing_user:
            print(f"❌ User '{username}' already exists!")
            return False

        # Check email if provided
        if email:
            result = await session.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none():
                print(f"❌ Email '{email}' already registered!")
                return False

        # Create new user
        hashed_password = get_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            is_superuser=is_superuser
        )
        session.add(new_user)
        await session.commit()
        await session.refresh(new_user)

        print(f"✅ User '{username}' created successfully!")
        print(f"   ID: {new_user.id}")
        print(f"   Email: {email or 'N/A'}")
        print(f"   Superuser: {is_superuser}")
        return True


async def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("Usage: python create_user.py <username> <password> [email] [--superuser]")
        print("\nExample:")
        print("  python create_user.py admin mypassword admin@example.com")
        print("  python create_user.py admin mypassword admin@example.com --superuser")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]
    email = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith('--') else None
    is_superuser = '--superuser' in sys.argv

    success = await create_user(username, password, email, is_superuser)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

