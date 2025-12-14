#!/bin/bash
# Comprehensive test script for Docker environment

set -e

echo "🧪 Полное тестирование системы в Docker"
echo "========================================"
echo ""

# Check if containers are running
echo "📦 Проверка контейнеров..."
if ! docker-compose ps | grep -q "Up"; then
    echo "❌ Контейнеры не запущены. Запустите: docker-compose up -d"
    exit 1
fi
echo "✅ Контейнеры запущены"
echo ""

# Test 1: Health check
echo "1️⃣  Health Check:"
docker-compose exec -T app python -c "
import requests
import json
r = requests.get('http://localhost:8000/health')
print(f'   Status: {r.status_code}')
print(f'   Response: {json.dumps(r.json(), indent=2)}')
"
echo ""

# Test 2: Register user
echo "2️⃣  Регистрация пользователя:"
docker-compose exec -T app python -c "
import requests
import json
r = requests.post('http://localhost:8000/api/auth/register',
                  json={'username':'testuser','password':'test123','email':'test@example.com'})
print(f'   Status: {r.status_code}')
if r.status_code == 200:
    print('   ✅ Регистрация успешна')
    print(f'   {json.dumps(r.json(), indent=2)}')
else:
    print(f'   Response: {r.text[:200]}')
"
echo ""

# Test 3: Login
echo "3️⃣  Вход в систему:"
TOKEN=$(docker-compose exec -T app python -c "
import requests
import json
import sys
r = requests.post('http://localhost:8000/api/auth/login',
                  json={'username':'testuser','password':'test123'})
if r.status_code == 200:
    token = r.json().get('access_token', '')
    print(token)
    sys.exit(0)
else:
    print('', file=sys.stderr)
    print(f'Login failed: {r.status_code}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
    echo "   ✅ Вход успешен"
    echo "   Token: ${TOKEN:0:50}..."
    echo ""

    # Test 4: Get current user
    echo "4️⃣  Получение информации о пользователе:"
    docker-compose exec -T app python -c "
import requests
import json
token = '$TOKEN'
headers = {'Authorization': f'Bearer {token}'}
r = requests.get('http://localhost:8000/api/auth/me', headers=headers)
print(f'   Status: {r.status_code}')
if r.status_code == 200:
    print('   ✅ Успешно')
    print(f'   {json.dumps(r.json(), indent=2)}')
else:
    print(f'   ❌ Ошибка: {r.text[:200]}')
    "
    echo ""

    # Test 5: Protected endpoint
    echo "5️⃣  Защищенный эндпоинт:"
    docker-compose exec -T app python -c "
import requests
import json
token = '$TOKEN'
headers = {'Authorization': f'Bearer {token}'}
r = requests.get('http://localhost:8000/api/search/documents?query=test', headers=headers)
print(f'   Status: {r.status_code}')
if r.status_code == 200:
    print('   ✅ Доступ разрешен')
    data = r.json()
    print(f'   Documents found: {data.get(\"count\", 0)}')
else:
    print(f'   Response: {r.text[:200]}')
    "
    echo ""
else
    echo "   ❌ Вход не удался"
    echo ""
fi

# Test 6: Test without token
echo "6️⃣  Тест без токена:"
docker-compose exec -T app python -c "
import requests
r = requests.get('http://localhost:8000/api/search/documents?query=test')
print(f'   Status: {r.status_code}')
if r.status_code == 401:
    print('   ✅ Защита работает (401 Unauthorized)')
else:
    print(f'   ⚠️  Неожиданный статус: {r.status_code}')
"
echo ""

# Test 7: Database check
echo "7️⃣  Проверка базы данных:"
docker-compose exec -T db psql -U invoiceparser -d invoiceparser -c "SELECT username, email, is_active FROM users LIMIT 5;" 2>&1 | grep -v "^-" | grep -v "row"
echo ""

echo "========================================"
echo "✅ Тестирование завершено"
echo ""
echo "🌐 Доступ к приложению:"
echo "   - Web Interface: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Health: http://localhost:8000/health"
echo ""

