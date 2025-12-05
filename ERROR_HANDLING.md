# Error Handling Documentation

## Overview

The Invoice Parser application now includes comprehensive error handling with user-friendly, actionable error messages in English. All error messages are designed to help users understand what went wrong and how to fix it.

## Error Types

### 1. ⚠️ API Quota Exceeded (HTTP 429)

**When it happens:**
- You've exceeded your Gemini API quota (free tier: 50 requests per day)
- Rate limit has been hit

**User message:**
```
⚠️ API Quota Exceeded: You have exceeded your Gemini API quota.
Please check your plan and billing details at
https://ai.google.dev/gemini-api/docs/rate-limits.
Free tier has 50 requests per day limit.
```

**How to fix:**
- Wait until your quota resets (usually daily)
- Upgrade to a paid plan at https://aistudio.google.com/app/apikey
- Use a different API key

---

### 2. 🔑 API Key Error (HTTP 401 from Gemini)

**When it happens:**
- Invalid Gemini API key
- Missing API key in .env file

**User message:**
```
🔑 API Key Error: Invalid or missing Gemini API key.
Please check your GEMINI_API_KEY in the .env file and restart the application.
```

**How to fix:**
1. Open your `.env` file
2. Ensure `GEMINI_API_KEY` is set correctly
3. Get a valid key from https://aistudio.google.com/app/apikey
4. Restart the Docker container: `docker-compose restart`

---

### 3. 🔐 Authentication Error (HTTP 401 from Web API)

**When it happens:**
- Invalid or missing web authorization token
- Token mismatch between .env and frontend settings

**User message:**
```
🔐 Authentication Error: Invalid authorization token.
Please check your settings and ensure you have entered the correct WEB_AUTH_TOKEN.
```

**How to fix:**
1. Click the settings icon ⚙️ in the bottom right corner
2. Enter the correct `WEB_AUTH_TOKEN` from your `.env` file
3. Click "Save"

**Note:** The settings modal will automatically open after this error.

---

### 4. 🚫 Access Denied (HTTP 403)

**When it happens:**
- API key doesn't have proper permissions
- API key is restricted

**User message:**
```
🚫 Access Denied: Your API key does not have proper permissions.
Please verify your Gemini API key at https://aistudio.google.com/app/apikey
```

**How to fix:**
1. Visit https://aistudio.google.com/app/apikey
2. Check your API key restrictions
3. Create a new unrestricted key if needed
4. Update `.env` and restart

---

### 5. ⏱️ Request Timeout (HTTP 504)

**When it happens:**
- Document is too large or complex
- API is slow to respond
- Network issues

**User message:**
```
⏱️ Request Timeout: The request took too long.
The document may be too large or complex.
Please try again or use a smaller file.
```

**How to fix:**
- Try a smaller/simpler document
- Reduce image resolution
- Check your internet connection
- Try again later

---

### 6. 🌐 Network Error (HTTP 503)

**When it happens:**
- Cannot connect to Gemini API
- Internet connection issues
- API is temporarily unavailable

**User message:**
```
🌐 Network Error: Cannot connect to the API.
Please check your internet connection and try again.
```

**How to fix:**
- Check your internet connection
- Verify Docker container can access the internet
- Check Gemini API status
- Try again in a few minutes

---

### 7. 📄 Invalid Request (HTTP 400)

**When it happens:**
- Unsupported file format
- Corrupted file
- Invalid file size

**User message:**
```
📄 Invalid Request: [specific error details]
```

**How to fix:**
- Ensure file format is supported (PDF, JPG, PNG, TIFF, BMP)
- Check file is not corrupted
- Verify file size is under 50MB

---

### 8. ❌ Generic Errors (HTTP 500+)

**When it happens:**
- Unexpected server errors
- Parsing failures
- Internal application errors

**User message:**
```
❌ Error: [specific error details].
Please try again or contact support.
```

**How to fix:**
- Try uploading the file again
- Check application logs: `docker-compose logs app`
- Report the issue with log details

---

## Error Display Features

### Frontend Features

1. **Clickable Links**: All URLs in error messages are automatically converted to clickable links
2. **Formatted Display**: Error messages are left-aligned with proper line wrapping
3. **Auto-open Settings**: Authentication errors automatically open the settings modal
4. **Icon Indicators**: Each error type has a unique emoji for quick identification

### Backend Features

1. **Error Classification**: All errors are classified by type
2. **Detailed Logging**: Full error details are logged for debugging
3. **Clean Messages**: Error messages are cleaned and formatted for user display
4. **HTTP Status Codes**: Appropriate HTTP status codes for each error type

---

## Configuration

### Environment Variables

Ensure these are set in your `.env` file:

```bash
# Gemini API Configuration
GEMINI_API_KEY=your_actual_api_key_here
GEMINI_MODEL=gemini-2.5-pro
GEMINI_TIMEOUT=120

# Web API Configuration
WEB_AUTH_TOKEN=your_secret_token_here
WEB_HOST=0.0.0.0
WEB_PORT=8000
```

---

## Logging

All errors are logged with full stack traces for debugging:

```bash
# View real-time logs
docker-compose logs -f app

# View last 100 lines
docker-compose logs --tail 100 app

# View logs in log file
cat logs/invoiceparser_$(date +%Y%m%d).log
```

---

## Testing Error Handling

### Test Authentication Error
1. Enter wrong token in settings
2. Try to parse a document
3. Should see authentication error

### Test Quota Exceeded
- Wait until you've used all your daily quota
- Should see quota exceeded message with helpful links

### Test Invalid File
1. Try uploading a .txt file
2. Should see unsupported format error

---

## Support

If you encounter an error not covered here:

1. **Check Logs**: `docker-compose logs app`
2. **Check Configuration**: Verify `.env` file settings
3. **Restart Container**: `docker-compose restart`
4. **Full Rebuild**: `docker-compose down && docker-compose up --build -d`

For persistent issues, include:
- Error message from UI
- Application logs
- Docker container status: `docker-compose ps`
- Environment details (OS, Docker version)



