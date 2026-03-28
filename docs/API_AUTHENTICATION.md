# API Authentication Reference — AgenteDeVoz

## Base URL

```
https://api.agentevoz.com/api/v1
```

## Authentication Methods

### Bearer Token (JWT)

All protected endpoints require a JWT access token in the `Authorization` header:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Obtaining Tokens

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "YourPassword1!"
}
```

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Refreshing Tokens

When the access token expires (after 30 minutes), use the refresh token:

```http
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJ..."
}
```

---

## API Endpoints

### Authentication

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/auth/register` | ✗ | Register new user |
| `POST` | `/auth/login` | ✗ | Login, get tokens |
| `POST` | `/auth/refresh` | ✗ | Refresh access token |
| `POST` | `/auth/logout` | ✓ | Logout, blacklist token |
| `POST` | `/auth/forgot-password` | ✗ | Request password reset |
| `POST` | `/auth/reset-password` | ✗ | Confirm password reset |
| `GET`  | `/auth/verify-email/{token}` | ✗ | Verify email address |
| `GET`  | `/auth/oauth/{provider}` | ✗ | OAuth2 redirect |
| `GET`  | `/auth/oauth/{provider}/callback` | ✗ | OAuth2 callback |

### Users

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/users/me` | ✓ | Get current user |
| `PUT`  | `/users/me` | ✓ | Update profile |
| `PUT`  | `/users/me/password` | ✓ | Change password |
| `DELETE` | `/users/me` | ✓ | Delete account |
| `GET`  | `/users/me/usage` | ✓ | Usage statistics |
| `GET`  | `/users/me/sessions` | ✓ | Active sessions |
| `POST` | `/users/me/logout-all` | ✓ | Logout all devices |

### Subscriptions

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/subscriptions/plans` | ✗ | List all plans |
| `GET`  | `/subscriptions/me` | ✓ | Current subscription |
| `POST` | `/subscriptions` | ✓ | Create subscription |
| `PUT`  | `/subscriptions/upgrade` | ✓ | Upgrade plan |
| `PUT`  | `/subscriptions/cancel` | ✓ | Cancel subscription |
| `GET`  | `/subscriptions/billing-portal` | ✓ | Stripe portal URL |
| `POST` | `/subscriptions/checkout` | ✓ | Create checkout session |

### Payments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/payments/history` | ✓ | Payment history |
| `GET`  | `/payments/{id}` | ✓ | Single payment |
| `POST` | `/payments/webhook/stripe` | ✗* | Stripe webhook |
| `POST` | `/payments/webhook/paypal` | ✗* | PayPal webhook |
| `GET`  | `/payments/invoices` | ✓ | Invoice list |
| `POST` | `/payments/refund/{id}` | Admin | Refund payment |

*Webhook endpoints authenticate via signature, not JWT.

### Licenses

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/licenses` | ✓ | List user's licenses |
| `POST` | `/licenses/activate` | ✓ | Activate license key |
| `POST` | `/licenses/validate` | ✓ | Validate license key |
| `DELETE` | `/licenses/{key}` | Admin | Revoke license |

### Voice API

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/voice/process` | ✓ | Process voice/text |
| `GET`  | `/voice/session/{id}` | ✓ | Get session |
| `DELETE` | `/voice/session/{id}` | ✓ | End session |
| `WS`   | `/ws/{session_id}` | ✓ | WebSocket stream |

### Admin

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET`  | `/admin/stats` | Admin | Global stats |
| `GET`  | `/admin/users` | Admin | List all users |
| `PUT`  | `/admin/users/{id}/status` | Admin | Activate/suspend |
| `PUT`  | `/admin/users/{id}/plan` | Admin | Change user plan |
| `POST` | `/admin/users/{id}/impersonate` | Admin | Impersonate user |
| `GET`  | `/admin/analytics/dashboard` | Admin | KPI dashboard |
| `GET`  | `/admin/analytics/growth` | Admin | User growth data |

---

## Request/Response Format

### Content-Type

```http
Content-Type: application/json
```

### Error Response Format

```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "status_code": 400
}
```

### Standard HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200` | OK |
| `201` | Created |
| `400` | Bad Request (validation error) |
| `401` | Unauthorized (missing/expired token) |
| `402` | Payment Required (quota exceeded) |
| `403` | Forbidden (insufficient permissions) |
| `404` | Not Found |
| `409` | Conflict (duplicate email) |
| `422` | Unprocessable Entity (invalid JSON) |
| `429` | Too Many Requests (rate limited) |
| `500` | Internal Server Error |

---

## Code Examples

### Python

```python
import httpx

BASE_URL = "https://api.agentevoz.com/api/v1"

# Login
resp = httpx.post(f"{BASE_URL}/auth/login", json={
    "email": "user@example.com",
    "password": "SecurePass1!"
})
tokens = resp.json()
access_token = tokens["access_token"]

# Get user profile
resp = httpx.get(f"{BASE_URL}/users/me", headers={
    "Authorization": f"Bearer {access_token}"
})
user = resp.json()
print(user["full_name"])

# Process voice
resp = httpx.post(f"{BASE_URL}/voice/process",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"text": "Hola, necesito información sobre mis pedidos", "language": "es"}
)
result = resp.json()
print(result["response_text"])
```

### cURL

```bash
# Login
TOKEN=$(curl -s -X POST https://api.agentevoz.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass1!"}' \
  | jq -r '.access_token')

# Call voice API
curl -X POST https://api.agentevoz.com/api/v1/voice/process \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hola", "language": "es"}'
```

### JavaScript / Node.js

```javascript
const BASE_URL = 'https://api.agentevoz.com/api/v1';

async function login(email, password) {
  const resp = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const { access_token, refresh_token } = await resp.json();
  return { access_token, refresh_token };
}

async function processVoice(token, text) {
  const resp = await fetch(`${BASE_URL}/voice/process`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ text, language: 'es' }),
  });
  return resp.json();
}
```

---

## OpenAPI / Swagger

Interactive API docs are available at:

```
https://api.agentevoz.com/docs          # Swagger UI
https://api.agentevoz.com/redoc         # ReDoc
https://api.agentevoz.com/openapi.json  # OpenAPI spec
```
