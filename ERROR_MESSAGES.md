# Error Messages - Client vs Admin View

## Overview

The error handling system has been redesigned to separate client-facing messages from technical details:

- **Clients** see short, user-friendly messages without technical jargon
- **Administrators** see detailed error codes and full stack traces in logs
- **No sensitive information** (API providers, internal systems) is exposed to clients

---

## Error Categories

### 1. Client-Side Errors (User Mistakes)

These errors are caused by user actions and show clear instructions on how to fix them.

#### File Format Errors

**What user sees:**
```
📄 Unsupported file format. Please upload PDF, JPG, PNG, TIFF or BMP files only.
```

**Admin logs:**
```
WARNING - Rejected file with unsupported extension: .txt
```

---

#### File Size Errors

**What user sees:**
```
📄 File is too large (75.3MB). Maximum file size is 50MB. Please use a smaller file.
```

**Admin logs:**
```
WARNING - Rejected file: too large (75.3MB)
```

---

#### Missing File

**What user sees:**
```
📄 Please select a file first
```

**Admin logs:**
```
INFO - Parse request without file selection
```

---

#### Authentication Error

**What user sees:**
```
🔐 Invalid authorization. Please check your credentials.
```

**Admin logs:**
```
WARNING - Unauthorized access attempt
```

*Note: Settings modal automatically opens for user to enter correct token.*

---

### 2. Technical Errors (Service Issues)

These errors are caused by technical problems. Users see generic messages, admins see full details.

#### E001 - Service Quota Exceeded

**What user sees:**
```
⚠️ Service temporarily unavailable due to high load. Please try again later.
```

**Admin logs:**
```
ERROR - AI API error: 429 Resource exhausted
ERROR - Full error details: google.api_core.exceptions.ResourceExhausted: 429 You exceeded your current quota
ERROR - ERROR_CODE: E001 - API quota exceeded
```

**Admin action:** Check API quota, upgrade plan, or wait for reset

---

#### E002 - API Authentication Error

**What user sees:**
```
⚙️ Service configuration error. Please contact support. [E002]
```

**Admin logs:**
```
ERROR - AI API error: 401 Unauthorized
ERROR - Full error details: Invalid API key
ERROR - ERROR_CODE: E002 - API authentication error
```

**Admin action:** Check GEMINI_API_KEY in .env file, verify it's valid

---

#### E003 - API Access Denied

**What user sees:**
```
⚙️ Service configuration error. Please contact support. [E003]
```

**Admin logs:**
```
ERROR - AI API error: 403 Forbidden
ERROR - Full error details: API key doesn't have permission
ERROR - ERROR_CODE: E003 - API access denied
```

**Admin action:** Check API key permissions, create new unrestricted key

---

#### E004 - Request Timeout

**What user sees:**
```
⏱️ Request timeout. Please try again with a smaller document.
```

**Admin logs:**
```
ERROR - AI API error: Timeout exceeded
ERROR - Full error details: Request timeout after 120 seconds
ERROR - ERROR_CODE: E004 - Request timeout
```

**Admin action:** Check document complexity, consider increasing timeout

---

#### E005 - Network Error

**What user sees:**
```
🌐 Network connection error. Please check your connection and try again.
```

**Admin logs:**
```
ERROR - AI API error: ConnectionError
ERROR - Full error details: Failed to establish connection
ERROR - ERROR_CODE: E005 - Network error
```

**Admin action:** Check internet connection, verify firewall rules, check API status

---

#### E099 - Unknown Error

**What user sees:**
```
❌ Unable to process document. Please try again or contact support. [E099]
```

**Admin logs:**
```
ERROR - AI API error: [detailed error message]
ERROR - Full error details: [complete stack trace]
ERROR - ERROR_CODE: E099 - Unknown error: [full details]
```

**Admin action:** Review logs, check for unusual patterns, report to development team

---

## Error Message Format

### Frontend Display

```
[Emoji] [User-friendly message] [Optional: Error code for technical errors]
```

Examples:
- `📄 File is too large (75.3MB). Maximum file size is 50MB.`
- `⚠️ Service temporarily unavailable due to high load. Please try again later.`
- `⚙️ Service configuration error. Please contact support. [E002]`

### Backend Logs

```
ERROR - AI API error: [exception message]
ERROR - Full error details: [complete error message]
ERROR - ERROR_CODE: [CODE] - [description]
```

### API Response Format

```json
{
  "error_code": "E001",
  "message": "Service temporarily unavailable due to high load. Please try again later."
}
```

---

## What Clients DON'T See

❌ "Gemini API"
❌ "quota exceeded"
❌ "API key"
❌ File paths or internal directory structure
❌ Stack traces
❌ Environment variables
❌ Third-party service names
❌ Technical implementation details

---

## What Clients DO See

✅ Clear, actionable messages
✅ File format requirements
✅ File size limits
✅ Suggestions to fix the problem
✅ When to contact support
✅ Visual indicators (emojis)

---

## Error Code Reference

| Code | Type | User Sees | Admin Action |
|------|------|-----------|--------------|
| E001 | Quota | Service unavailable | Check API quota |
| E002 | Auth | Config error + code | Check API key |
| E003 | Access | Config error + code | Check API permissions |
| E004 | Timeout | Timeout message | Check document size/timeout settings |
| E005 | Network | Connection error | Check network/firewall |
| E099 | Unknown | Generic error + code | Review logs, investigate |

---

## Viewing Admin Logs

### Docker Logs

```bash
# Real-time logs
docker-compose logs -f app

# Last 100 lines
docker-compose logs --tail 100 app

# Search for specific error
docker-compose logs app | grep "ERROR_CODE"

# Search for specific error code
docker-compose logs app | grep "E001"
```

### Log Files

```bash
# Today's log
cat logs/invoiceparser_$(date +%Y%m%d).log

# Search for errors
grep "ERROR_CODE" logs/invoiceparser_*.log

# View last 50 errors
grep "ERROR" logs/invoiceparser_*.log | tail -50
```

---

## Testing Error Messages

### Test Client Errors

1. **Wrong file format:**
   - Upload a .txt or .docx file
   - Should see: "Unsupported file format"

2. **File too large:**
   - Upload 50MB+ file
   - Should see: "File is too large"

3. **Invalid auth token:**
   - Enter wrong token
   - Should see: "Invalid authorization"

### Test Technical Errors

1. **Quota exceeded:**
   - Use all daily quota
   - User sees: "Service temporarily unavailable"
   - Logs show: "ERROR_CODE: E001"

2. **Invalid API key:**
   - Set wrong key in .env
   - User sees: "Service configuration error [E002]"
   - Logs show: "ERROR_CODE: E002"

---

## Benefits

### For Clients:
- ✅ Clear, understandable messages
- ✅ No confusing technical jargon
- ✅ Actionable instructions
- ✅ Professional appearance
- ✅ Privacy of internal systems

### For Administrators:
- ✅ Complete error details in logs
- ✅ Error codes for quick identification
- ✅ Full stack traces for debugging
- ✅ Easy to search and filter
- ✅ Detailed context for troubleshooting

### For Business:
- ✅ Professional user experience
- ✅ Protected intellectual property
- ✅ No exposure of infrastructure details
- ✅ Easier support (error codes)
- ✅ Better security

---

## Security Considerations

The new error handling system improves security by:

1. **No Information Leakage**
   - Clients don't see API providers used
   - No file paths or system structure exposed
   - No configuration details revealed

2. **Rate Limit Protection**
   - Generic message doesn't reveal quota limits
   - No information about usage patterns

3. **Authentication Privacy**
   - No details about authentication mechanisms
   - No hints about valid vs invalid credentials

4. **System Architecture**
   - No exposure of internal service names
   - No details about third-party integrations

---

## Support Workflow

When a client reports an error:

1. **Client provides:** Error message and error code (if shown)
2. **Support checks:** Admin logs using error code
3. **Support sees:** Full technical details and stack trace
4. **Support resolves:** Based on complete information
5. **Client receives:** Solution without technical details

Example:
```
Client: "I got error: Service configuration error [E002]"
Support: *Checks logs, sees "Invalid API key"*
Support: "We've fixed a configuration issue. Please try again."
Client: *Successfully uploads and parses document*
```

---

## Configuration

No additional configuration needed. The error handling works automatically.

### Environment Variables

Make sure these are set correctly in `.env`:

```bash
# API Configuration (admin only)
GEMINI_API_KEY=your_key_here

# Web Authentication (shared with users)
WEB_AUTH_TOKEN=your_token_here
```

---

## Best Practices

### For Administrators:

1. **Monitor logs regularly** for error codes
2. **Set up alerts** for E002/E003 (config errors)
3. **Track E001** (quota) to plan capacity
4. **Review E099** (unknown errors) for patterns

### For Support Team:

1. **Ask for error codes** when users report issues
2. **Use error codes** to search logs quickly
3. **Translate technical issues** into user-friendly language
4. **Update FAQ** based on common error patterns

### For Developers:

1. **Keep error codes consistent**
2. **Log all technical details** for debugging
3. **Test error messages** from user perspective
4. **Update documentation** when adding new error types

---

**Version:** 2.0.0
**Last Updated:** 2024-12-04
**Status:** Production Ready ✅



