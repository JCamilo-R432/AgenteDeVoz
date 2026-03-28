# Authentication Guide — AgenteDeVoz

## Overview

AgenteDeVoz uses a layered authentication system:

1. **JWT Bearer tokens** for API authentication (HS256, 30-min access / 7-day refresh)
2. **bcrypt** for secure password hashing (cost factor 12)
3. **OAuth2** social login (Google, Microsoft)
4. **OTP tokens** for password reset and email verification

---

## Endpoints

### Register

```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass1!",
  "full_name": "Juan García",
  "company_name": "Empresa SA"  // optional
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Login

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass1!"
}
```

> **Demo mode:** Any email + password `Demo1234!` succeeds without a database.

### Refresh Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

### Logout

```http
POST /api/v1/auth/logout
Authorization: Bearer <access_token>
```

Blacklists the current JTI so the token cannot be reused.

### Forgot Password

```http
POST /api/v1/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

Always returns 200 (prevents email enumeration). Sends reset email if address exists.

### Reset Password

```http
POST /api/v1/auth/reset-password
Content-Type: application/json

{
  "token": "<reset_token_from_email>",
  "new_password": "NewPass1234!"
}
```

### Email Verification

```http
GET /api/v1/auth/verify-email/{token}
```

---

## OAuth2 Social Login

### Initiate flow

```
GET /api/v1/auth/oauth/google
GET /api/v1/auth/oauth/microsoft
```

Redirects to provider authorization page.

### Callback (automatic)

```
GET /api/v1/auth/oauth/google/callback?code=...&state=...
```

On success, redirects to `/dashboard` with tokens set in `localStorage`.

### Configuration

```env
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
MICROSOFT_CLIENT_ID=your_microsoft_client_id
MICROSOFT_CLIENT_SECRET=your_microsoft_client_secret
```

---

## Using Bearer Tokens

Include the access token in every protected request:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

JavaScript example:
```javascript
const token = localStorage.getItem('access_token');
const resp = await fetch('/api/v1/users/me', {
  headers: { 'Authorization': 'Bearer ' + token }
});
```

---

## Token Lifecycle

```
Register/Login
     │
     ▼
access_token (30 min)  ←──────────────────────────────┐
refresh_token (7 days)                                 │
     │                                               Refresh
     │ expires after 30 min                          (POST /auth/refresh)
     ▼                                                 │
401 Unauthorized ──────────────────────────────────────┘
     │
     │ refresh_token also expired
     ▼
Redirect to /login
```

---

## Password Policy

Passwords must contain:
- Minimum **8 characters**
- At least **1 uppercase** letter (A-Z)
- At least **1 digit** (0-9)

Recommendations:
- Use a symbol (`!@#$%`)
- Avoid dictionary words
- Never reuse passwords

---

## Security Headers

All protected responses include:

| Header | Value |
|--------|-------|
| `X-Trace-Id` | Unique request trace ID for audit logs |
| `X-RateLimit-Limit` | Requests allowed per minute |
| `X-RateLimit-Remaining` | Remaining requests this window |

---

## Rate Limiting

- **60 requests/minute** per IP (default)
- **10 burst** requests allowed
- Redis-backed (in-memory fallback if Redis unavailable)
- Exceeding limit returns `429 Too Many Requests`

---

## Admin Access

Admin endpoints require `is_admin: true` in the JWT payload:

```http
GET /api/v1/admin/stats
Authorization: Bearer <admin_token>
```

Admins can impersonate users (15-minute tokens):

```http
POST /api/v1/admin/users/{user_id}/impersonate
Authorization: Bearer <admin_token>
```

---

## Environment Variables

```env
SECRET_KEY=your-secret-key-min-32-chars
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
MAX_LOGIN_ATTEMPTS=5
REDIS_URL=redis://localhost:6379
```

---

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Token expired or missing | Refresh token or re-login |
| `403 Forbidden` | Not admin | Use an admin account |
| `429 Too Many Requests` | Rate limit exceeded | Wait 1 minute |
| `400 Invalid token` | Tampered or wrong-key token | Re-login |
