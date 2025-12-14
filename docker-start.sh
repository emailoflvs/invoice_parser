#!/bin/bash
# Quick start script for Docker Compose

set -e

echo "🚀 Starting Invoice Parser with Docker Compose..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it and set JWT_SECRET_KEY!"
        echo "   Then run this script again."
        exit 1
    else
        echo "❌ .env.example not found. Please create .env file manually."
        exit 1
    fi
fi

# Build and start
echo "📦 Building and starting containers..."
docker-compose up -d --build

# Wait for app to be ready
echo "⏳ Waiting for application to start..."
sleep 5

# Check if app is running
if docker-compose ps app | grep -q "Up"; then
    echo "✅ Application is running!"
    echo ""
    echo "📝 Next steps:"
    echo "   1. Create first user:"
    echo "      docker-compose exec app python scripts/create_user.py admin your_password admin@example.com --superuser"
    echo ""
    echo "   2. View logs:"
    echo "      docker-compose logs -f app"
    echo ""
    echo "   3. Access web interface:"
    echo "      http://localhost:8000"
    echo ""
    echo "   4. API documentation:"
    echo "      http://localhost:8000/docs"
else
    echo "❌ Application failed to start. Check logs:"
    echo "   docker-compose logs app"
    exit 1
fi

