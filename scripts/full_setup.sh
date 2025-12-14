#!/bin/bash
# Full setup script - configures .env, database, and creates first user

set -e

echo "🚀 Full Setup Script for Invoice Parser"
echo "========================================"
echo ""

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Step 1: Setup .env file
echo "📝 Step 1: Configuring .env file..."
python3 scripts/setup_env.py
echo ""

# Step 2: Check if Docker is running
echo "🐳 Step 2: Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi
echo "✅ Docker is running"
echo ""

# Step 3: Start database
echo "🗄️  Step 3: Starting database..."
docker-compose up -d db
echo "⏳ Waiting for database to be ready..."
sleep 5

# Wait for database
for i in {1..30}; do
    if docker-compose exec -T db pg_isready -U invoiceparser > /dev/null 2>&1; then
        echo "✅ Database is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Database failed to start after 60 seconds"
        exit 1
    fi
    echo "   Waiting... ($i/30)"
    sleep 2
done
echo ""

# Step 4: Build and start application
echo "🔨 Step 4: Building application..."
docker-compose build app
echo ""

echo "🚀 Step 5: Starting application..."
docker-compose up -d app
echo "⏳ Waiting for application to start..."
sleep 10
echo ""

# Step 5: Check if migrations ran
echo "📦 Step 6: Checking database migrations..."
if docker-compose exec -T app python -m alembic current > /dev/null 2>&1; then
    echo "✅ Migrations completed"
else
    echo "⚠️  Migrations may still be running. Check logs: docker-compose logs app"
fi
echo ""

# Step 6: Create first user
echo "👤 Step 7: Creating first user..."
echo ""
read -p "Enter username for admin user (default: admin): " username
username=${username:-admin}

read -sp "Enter password for admin user: " password
echo ""

read -p "Enter email for admin user (optional): " email

if [ -z "$password" ]; then
    echo "❌ Password cannot be empty"
    exit 1
fi

if docker-compose exec -T app python scripts/create_user.py "$username" "$password" "$email" --superuser; then
    echo ""
    echo "✅ Admin user created successfully!"
else
    echo ""
    echo "⚠️  Failed to create user. You can create it manually:"
    echo "   docker-compose exec app python scripts/create_user.py <username> <password> [email] [--superuser]"
fi
echo ""

# Final summary
echo "========================================"
echo "✅ Setup Complete!"
echo ""
echo "📋 Summary:"
echo "   - .env file configured"
echo "   - Database started"
echo "   - Application running"
echo "   - Admin user created"
echo ""
echo "🌐 Access your application:"
echo "   - Web Interface: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Health Check: http://localhost:8000/health"
echo ""
echo "📝 Useful commands:"
echo "   - View logs: docker-compose logs -f app"
echo "   - Stop: docker-compose down"
echo "   - Restart: docker-compose restart app"
echo ""

