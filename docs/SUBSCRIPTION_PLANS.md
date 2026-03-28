# Subscription Plans — AgenteDeVoz

## Plan Overview

| Feature | Free | Basic | Pro | Enterprise |
|---------|------|-------|-----|-----------|
| **Price** | $0/mo | $29/mo | $99/mo | $499/mo |
| **Calls/month** | 50 | 500 | 2,000 | Unlimited |
| **Concurrent sessions** | 1 | 3 | 10 | Unlimited |
| **Max call duration** | 5 min | 15 min | 30 min | Unlimited |
| **Storage** | 1 GB | 10 GB | 50 GB | 500 GB |
| **API requests/day** | 100 | 1,000 | 10,000 | Unlimited |
| **Priority support** | ✗ | ✗ | ✓ | ✓ |
| **SLA guarantee** | ✗ | ✗ | ✗ | ✓ |
| **Trial period** | — | 14 days | 14 days | 14 days |

---

## Free Plan

- **Target:** Developers evaluating the platform
- **Limits:** 50 voice calls/month, 100 API req/day
- **No credit card required**
- Resets on the 1st of each month

## Basic Plan — $29/month

- **Target:** Small teams and startups
- **Includes:** 500 calls, 3 concurrent sessions, 15 min/call
- Billed monthly or yearly (-20%)
- 14-day free trial included

## Pro Plan — $99/month ⭐

- **Target:** Growing businesses
- **Includes:** 2,000 calls, 10 concurrent sessions, 30 min/call
- Priority support via chat and email
- Billed monthly or yearly (-20%)
- 14-day free trial included

## Enterprise Plan — $499/month

- **Target:** Large enterprises requiring SLA
- **Includes:** Unlimited everything + 500 GB storage
- Dedicated account manager
- SLA with 99.9% uptime guarantee
- Custom integrations available
- Annual billing with custom pricing for large volumes

---

## Billing Cycles

### Monthly
- Charged on the same day each month
- Cancel anytime — access until period end

### Yearly (Annual)
- **20% discount** compared to monthly
- Paid upfront for 12 months
- Prorated refund available in first 30 days

---

## Quota Enforcement

### How quotas work

1. Each successful voice call increments `monthly_call_count`
2. At **80% usage**, users receive an email warning
3. At **100% usage**, new calls return `402 Payment Required`
4. Counters reset automatically on the 1st of each month

### Quota exceeded response

```json
{
  "detail": "Monthly call quota exceeded. Upgrade your plan to continue.",
  "error_code": "QUOTA_EXCEEDED",
  "current_plan": "free",
  "calls_used": 50,
  "calls_limit": 50,
  "upgrade_url": "/pricing"
}
```

### Enterprise unlimited

Plans with `monthly_call_limit = -1` bypass all quota checks.

---

## Plan Upgrades & Downgrades

### Upgrade (immediate)
```http
PUT /api/v1/subscriptions/upgrade
Authorization: Bearer <token>

{ "plan_id": "pro", "billing_cycle": "monthly" }
```

- New plan takes effect immediately
- Prorated credit applied for unused days

### Downgrade (end of period)
```http
PUT /api/v1/subscriptions/cancel
Authorization: Bearer <token>
```

- Downgrade scheduled for end of current billing period
- User retains current plan features until then

---

## Trial Periods

- All paid plans include a **14-day free trial**
- No credit card required during trial
- Full plan features available during trial
- Converts automatically at trial end (if payment method provided)
- Cancel before trial ends — no charge

---

## API Reference

### Get all plans
```http
GET /api/v1/subscriptions/plans
```

### Get current subscription
```http
GET /api/v1/subscriptions/me
Authorization: Bearer <token>
```

### Create/upgrade subscription
```http
POST /api/v1/subscriptions
PUT /api/v1/subscriptions/upgrade
Authorization: Bearer <token>
```

### Stripe checkout
```http
POST /api/v1/subscriptions/checkout
Authorization: Bearer <token>

{
  "plan_id": "pro",
  "billing_cycle": "monthly",
  "payment_provider": "stripe"
}
```

---

## Configuration

```python
# config/subscription_config.py
PLAN_LIMITS = {
    "free":       {"monthly_calls": 50,    "concurrent_sessions": 1,  "api_requests_per_day": 100},
    "basic":      {"monthly_calls": 500,   "concurrent_sessions": 3,  "api_requests_per_day": 1000},
    "pro":        {"monthly_calls": 2000,  "concurrent_sessions": 10, "api_requests_per_day": 10000},
    "enterprise": {"monthly_calls": -1,    "concurrent_sessions": -1, "api_requests_per_day": -1},
}

PLAN_PRICES = {
    "basic":      {"monthly": 29.00,  "yearly": 278.40},
    "pro":        {"monthly": 99.00,  "yearly": 950.40},
    "enterprise": {"monthly": 499.00, "yearly": 4790.40},
}
```
