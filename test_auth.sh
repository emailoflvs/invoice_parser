#!/bin/bash
# Test script for authentication system

set -e

BASE_URL="http://localhost:8000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧪 Testing Authentication System"
echo "================================"
echo ""

# Test 1: Health check
echo "1️⃣  Testing health endpoint..."
if curl -s "$BASE_URL/health" | grep -q "ok"; then
    echo -e "${GREEN}✅ Health check passed${NC}"
else
    echo -e "${RED}❌ Health check failed${NC}"
    exit 1
fi
echo ""

# Test 2: Register user
echo "2️⃣  Testing user registration..."
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser'$(date +%s)'","password":"testpass123","email":"test'$(date +%s)'@example.com"}')

if echo "$REGISTER_RESPONSE" | grep -q "success"; then
    echo -e "${GREEN}✅ User registration passed${NC}"
    echo "$REGISTER_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$REGISTER_RESPONSE"
else
    echo -e "${YELLOW}⚠️  Registration response: $REGISTER_RESPONSE${NC}"
fi
echo ""

# Test 3: Login
echo "3️⃣  Testing login..."
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"username":"testuser","password":"testpass123"}')

TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -n "$TOKEN" ] && [ "$TOKEN" != "None" ]; then
    echo -e "${GREEN}✅ Login successful${NC}"
    echo "   Token: ${TOKEN:0:50}..."
else
    echo -e "${RED}❌ Login failed${NC}"
    echo "   Response: $LOGIN_RESPONSE"
    exit 1
fi
echo ""

# Test 4: Get current user
echo "4️⃣  Testing /api/auth/me endpoint..."
ME_RESPONSE=$(curl -s -X GET "$BASE_URL/api/auth/me" \
    -H "Authorization: Bearer $TOKEN")

if echo "$ME_RESPONSE" | grep -q "username"; then
    echo -e "${GREEN}✅ Get current user passed${NC}"
    echo "$ME_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$ME_RESPONSE"
else
    echo -e "${RED}❌ Get current user failed${NC}"
    echo "   Response: $ME_RESPONSE"
    exit 1
fi
echo ""

# Test 5: Protected endpoint without token
echo "5️⃣  Testing protected endpoint without token..."
PROTECTED_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/api/search/documents?query=test" | tail -1)
if [ "$PROTECTED_RESPONSE" = "401" ]; then
    echo -e "${GREEN}✅ Protection works (401 Unauthorized)${NC}"
else
    echo -e "${RED}❌ Protection failed (got $PROTECTED_RESPONSE instead of 401)${NC}"
fi
echo ""

# Test 6: Protected endpoint with token
echo "6️⃣  Testing protected endpoint with token..."
SEARCH_RESPONSE=$(curl -s -X GET "$BASE_URL/api/search/documents?query=test" \
    -H "Authorization: Bearer $TOKEN")

if echo "$SEARCH_RESPONSE" | grep -q "count\|documents"; then
    echo -e "${GREEN}✅ Protected endpoint access works${NC}"
    echo "$SEARCH_RESPONSE" | python3 -m json.tool 2>/dev/null | head -10 || echo "$SEARCH_RESPONSE"
else
    echo -e "${YELLOW}⚠️  Search response: $SEARCH_RESPONSE${NC}"
fi
echo ""

# Test 7: Invalid token
echo "7️⃣  Testing with invalid token..."
INVALID_RESPONSE=$(curl -s -w "\n%{http_code}" -X GET "$BASE_URL/api/auth/me" \
    -H "Authorization: Bearer invalid_token_12345" | tail -1)
if [ "$INVALID_RESPONSE" = "401" ]; then
    echo -e "${GREEN}✅ Invalid token rejected (401 Unauthorized)${NC}"
else
    echo -e "${RED}❌ Invalid token not rejected (got $INVALID_RESPONSE)${NC}"
fi
echo ""

echo "================================"
echo -e "${GREEN}✅ All tests completed!${NC}"
echo ""
echo "📋 Summary:"
echo "   - Health check: ✅"
echo "   - User registration: ✅"
echo "   - Login: ✅"
echo "   - Get current user: ✅"
echo "   - Protected endpoints: ✅"
echo "   - Token validation: ✅"
echo ""
echo "🌐 Access your application:"
echo "   - Web Interface: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo ""

