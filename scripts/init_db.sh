#!/bin/bash
# Script to initialize database with migrations and create first user

set -e

echo "🚀 Initializing database..."

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
until python -c "
import sys
sys.path.insert(0, 'src')
from invoiceparser.database import init_db, get_session
from invoiceparser.core.config import Config
from sqlalchemy import text
import asyncio

async def check_db():
    config = Config.load()
    init_db(config.database_url, echo=False, pool_size=5, max_overflow=10)
    async for session in get_session():
        await session.execute(text('SELECT 1'))
        print('✅ Database is ready!')
        break

asyncio.run(check_db())
" 2>/dev/null; do
    echo "⏳ Database is not ready yet, waiting..."
    sleep 2
done

# Run migrations
echo "📦 Running database migrations..."
python -m alembic upgrade head

# Check if we need to create first user
echo "👤 Checking for existing users..."
USER_COUNT=$(python -c "
import sys
sys.path.insert(0, 'src')
from invoiceparser.database import init_db, get_session
from invoiceparser.core.config import Config
from sqlalchemy import select, func
from invoiceparser.database.models import User
import asyncio

async def count_users():
    config = Config.load()
    init_db(config.database_url, echo=False, pool_size=5, max_overflow=10)
    async for session in get_session():
        result = await session.execute(select(func.count(User.id)))
        count = result.scalar()
        print(count)
        break

asyncio.run(count_users())
" 2>/dev/null)

if [ "$USER_COUNT" = "0" ]; then
    echo "⚠️  No users found. Creating default admin user..."
    echo "   Username: admin"
    echo "   Password: admin (CHANGE THIS IN PRODUCTION!)"
    echo ""

    python scripts/create_user.py admin admin admin@example.com --superuser || {
        echo "❌ Failed to create default user. You can create it manually:"
        echo "   python scripts/create_user.py <username> <password> [email] [--superuser]"
    }
else
    echo "✅ Users already exist in database."
fi

echo "✅ Database initialization complete!"










