# Admin Guide — AgenteDeVoz

## Overview

The AgenteDeVoz admin panel provides full control over users, subscriptions, payments, and analytics.

**Admin panel URL:** `/admin`
**API base:** `/api/v1/admin`

---

## Getting Admin Access

### Create first admin user

```bash
python scripts/create_admin.py \
  --email admin@yourdomain.com \
  --password Admin1234! \
  --name "Admin User"
```

### Promote existing user

```bash
python scripts/create_admin.py \
  --email existing@example.com \
  --promote-only
```

### Default admin (demo mode)

When no database is connected, the default admin credentials are:

- **Email:** `admin@agentevoz.com`
- **Password:** `Admin1234!`

---

## Admin Panel Sections

### Dashboard (`/admin`)

Key performance indicators:

| Metric | Description |
|--------|-------------|
| **MRR** | Monthly Recurring Revenue |
| **ARR** | Annual Recurring Revenue (MRR × 12) |
| **Total Users** | All registered users |
| **Churn Rate** | Monthly cancellation rate |
| **New Users Today** | Registrations in the last 24h |
| **Plan Distribution** | Users by subscription plan |

Visual charts:
- 30-day user growth (daily)
- Revenue by plan breakdown

### Users (`/admin/users`)

Features:
- Search by email or name
- Filter by subscription plan
- Paginated table (20 users/page)
- Per-user actions:
  - **Change plan** — immediate plan change
  - **Suspend/Activate** — block or restore access
  - **Impersonate** — log in as the user (15-min session)

### Subscriptions (`/admin/subscriptions`)

- Filter by status (active, trialing, past_due, cancelled)
- Per-subscription actions:
  - **Extend** — add N days to the current period
  - **Cancel** — cancel the subscription

### Payments (`/admin/payments`)

- Search by email or payment ID
- Filter by payment provider
- Per-payment actions:
  - **Download invoice** (PDF)
  - **Refund** — process full refund

---

## Admin API Reference

### Analytics Dashboard

```http
GET /api/v1/admin/analytics/dashboard
Authorization: Bearer <admin_token>
```

Response:
```json
{
  "mrr": 12480,
  "arr": 149760,
  "mrr_growth_pct": 8.3,
  "total_users": 342,
  "active_users": 298,
  "new_users_today": 5,
  "churn_rate": 2.4,
  "plan_distribution": [
    {"plan": "free", "count": 210, "pct": 61},
    {"plan": "basic", "count": 78, "pct": 23},
    {"plan": "pro", "count": 42, "pct": 12},
    {"plan": "enterprise", "count": 12, "pct": 4}
  ],
  "revenue_by_plan": [
    {"plan": "Enterprise", "revenue": 5988},
    {"plan": "Pro", "revenue": 4158}
  ]
}
```

### User Growth

```http
GET /api/v1/admin/analytics/growth?days=30
Authorization: Bearer <admin_token>
```

### List Users

```http
GET /api/v1/admin/users?page=1&limit=20&plan=pro
Authorization: Bearer <admin_token>
```

### Change User Plan

```http
PUT /api/v1/admin/users/{user_id}/plan
Authorization: Bearer <admin_token>
Content-Type: application/json

{ "plan_id": "enterprise" }
```

### Suspend / Activate User

```http
PUT /api/v1/admin/users/{user_id}/status
Authorization: Bearer <admin_token>
Content-Type: application/json

{ "action": "suspend" }   // or "activate"
```

### Impersonate User

```http
POST /api/v1/admin/users/{user_id}/impersonate
Authorization: Bearer <admin_token>
```

Response:
```json
{
  "access_token": "eyJ...",
  "expires_in": 900,
  "note": "Token expires in 15 minutes"
}
```

### Extend Subscription

```http
POST /api/v1/admin/subscriptions/{sub_id}/extend
Authorization: Bearer <admin_token>
Content-Type: application/json

{ "days": 30 }
```

---

## Maintenance Scripts

### Reset monthly quotas

Run at the start of each billing cycle:

```bash
python scripts/migrate_users.py --reset-quotas
```

### Fix mismatched plan limits

After bulk plan changes:

```bash
python scripts/migrate_users.py --fix-limits
```

### Migrate users between plans

```bash
python scripts/migrate_users.py \
  --from-plan basic \
  --to-plan pro \
  --email-domain bigclient.com
```

### Generate license keys

```bash
# 100 Pro keys
python scripts/generate_license_keys.py --plan pro --count 100 --output pro_keys.txt

# All plans, 20 keys each
python scripts/generate_license_keys.py --all-plans --count 20
```

### Dry-run migration report

```bash
python scripts/migrate_users.py --dry-run
```

---

## Security Best Practices

1. **Never share admin credentials** — each admin should have their own account
2. **Use strong passwords** — minimum 12 characters for admin accounts
3. **Review impersonation logs** — all impersonations are recorded in audit logs
4. **Rotate SECRET_KEY regularly** — invalidates all existing tokens
5. **Monitor admin API calls** via `X-Trace-Id` headers in audit logs
6. **Restrict admin access by IP** — configure firewall if needed

---

## Audit Logs

All admin actions are logged with:

```
AUDIT {trace_id} {admin_user_id} {action} {target_user_id} {timestamp}
```

Example:
```
AUDIT abc123 user_admin plan_change user_456 2026-03-23T14:32:00Z
```

Access audit logs in your log aggregation system (Elasticsearch, Grafana Loki, etc.).

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| Can't access `/admin` | Not logged in as admin | Use `create_admin.py` to ensure `is_admin=True` |
| "Access denied" on API | JWT missing `is_admin: true` | Re-login after promoting user |
| Impersonation not working | Feature disabled | Check admin panel settings |
| Analytics showing zeros | No DB connected | Run `database/seeders/initial_data.py` |
| User count incorrect | Cache stale | Restart the application |
