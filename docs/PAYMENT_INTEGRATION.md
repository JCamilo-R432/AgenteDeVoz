# Payment Integration Guide — AgenteDeVoz

## Supported Providers

| Provider | Use Case | Region |
|----------|----------|--------|
| **Stripe** | Cards, subscriptions, billing portal | Global |
| **PayPal** | PayPal wallet, Pay Later | Global |
| **MercadoPago** | Cards, cash, bank transfer | LATAM |

---

## Stripe Integration

### Setup

```env
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_FREE_MONTHLY=price_...
STRIPE_PRICE_BASIC_MONTHLY=price_...
STRIPE_PRICE_PRO_MONTHLY=price_...
STRIPE_PRICE_ENTERPRISE_MONTHLY=price_...
STRIPE_PRICE_BASIC_YEARLY=price_...
STRIPE_PRICE_PRO_YEARLY=price_...
STRIPE_PRICE_ENTERPRISE_YEARLY=price_...
```

### Create Stripe Products/Prices

In the Stripe Dashboard or CLI:

```bash
stripe products create --name="AgenteDeVoz Basic"
stripe prices create \
  --product=prod_xxx \
  --unit-amount=2900 \
  --currency=usd \
  --recurring[interval]=month
```

### Checkout Flow

1. User selects plan → `POST /api/v1/subscriptions/checkout`
2. Backend creates Stripe Checkout Session
3. User redirected to `checkout.stripe.com`
4. On success → Stripe calls webhook → subscription activated
5. User redirected to `/dashboard?upgraded=1`

```python
# Example: create checkout session
session = stripe.checkout.Session.create(
    customer=stripe_customer_id,
    payment_method_types=["card"],
    line_items=[{"price": price_id, "quantity": 1}],
    mode="subscription",
    trial_period_days=14,
    success_url=f"{BASE_URL}/dashboard?upgraded=1",
    cancel_url=f"{BASE_URL}/pricing",
)
```

### Billing Portal

Users can manage their payment method and invoices:

```http
GET /api/v1/subscriptions/billing-portal
Authorization: Bearer <token>
```

Returns a Stripe Billing Portal URL.

---

## Stripe Webhooks

### Register webhook endpoint

```bash
stripe listen --forward-to localhost:8000/api/v1/payments/webhook/stripe
```

Or in Stripe Dashboard → Webhooks → Add endpoint: `https://yourdomain.com/api/v1/payments/webhook/stripe`

### Events handled

| Event | Action |
|-------|--------|
| `payment_intent.succeeded` | Record payment, send receipt email |
| `payment_intent.payment_failed` | Mark payment failed, notify user |
| `customer.subscription.created` | Activate subscription in DB |
| `customer.subscription.updated` | Sync subscription status |
| `customer.subscription.deleted` | Cancel subscription, downgrade plan |
| `invoice.payment_succeeded` | Update next billing date |
| `invoice.payment_failed` | Set status to `past_due` |

### Webhook signature verification

```python
import stripe

event = stripe.Webhook.construct_event(
    payload=request.body,
    sig_header=request.headers["Stripe-Signature"],
    secret=STRIPE_WEBHOOK_SECRET,
)
```

---

## PayPal Integration

### Setup

```env
PAYPAL_CLIENT_ID=your_paypal_client_id
PAYPAL_SECRET=your_paypal_secret
PAYPAL_MODE=sandbox  # or "live"
```

### OAuth token

```python
import requests, base64

credentials = base64.b64encode(f"{CLIENT_ID}:{SECRET}".encode()).decode()
resp = requests.post(
    "https://api-m.sandbox.paypal.com/v1/oauth2/token",
    headers={"Authorization": f"Basic {credentials}"},
    data={"grant_type": "client_credentials"},
)
access_token = resp.json()["access_token"]
```

### Create order

```http
POST https://api-m.sandbox.paypal.com/v2/checkout/orders
Authorization: Bearer <access_token>

{
  "intent": "CAPTURE",
  "purchase_units": [{
    "amount": {"currency_code": "USD", "value": "99.00"},
    "description": "AgenteDeVoz Pro Plan"
  }],
  "application_context": {
    "return_url": "https://yourapp.com/api/v1/payments/webhook/paypal/success",
    "cancel_url": "https://yourapp.com/pricing"
  }
}
```

### Webhook endpoint

```
POST /api/v1/payments/webhook/paypal
```

---

## MercadoPago Integration

### Setup

```env
MERCADOPAGO_ACCESS_TOKEN=your_mp_access_token
```

### Create preference (hosted checkout)

```python
import mercadopago

sdk = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)
preference_data = {
    "items": [{"title": "Plan Pro AgenteDeVoz", "quantity": 1, "unit_price": 99.0}],
    "back_urls": {
        "success": f"{BASE_URL}/dashboard?upgraded=1",
        "failure": f"{BASE_URL}/pricing?error=1",
    },
    "auto_return": "approved",
    "notification_url": f"{BASE_URL}/api/v1/payments/webhook/mercadopago",
}
preference = sdk.preference().create(preference_data)
checkout_url = preference["response"]["init_point"]
```

---

## Payment Routes Reference

```http
# Payment history
GET /api/v1/payments/history
Authorization: Bearer <token>

# Single payment
GET /api/v1/payments/{payment_id}
Authorization: Bearer <token>

# Stripe webhook
POST /api/v1/payments/webhook/stripe
Stripe-Signature: t=...,v1=...

# PayPal webhook
POST /api/v1/payments/webhook/paypal

# Download invoices
GET /api/v1/payments/invoices
Authorization: Bearer <token>

# Refund (admin only)
POST /api/v1/payments/refund/{payment_id}
Authorization: Bearer <admin_token>
```

---

## Testing Payments

### Stripe test cards

| Card number | Scenario |
|-------------|----------|
| `4242 4242 4242 4242` | Success |
| `4000 0000 0000 9995` | Insufficient funds |
| `4000 0025 0000 3155` | 3D Secure required |

Use any future expiry date, any 3-digit CVV.

### PayPal sandbox

Use sandbox accounts from developer.paypal.com.

### MercadoPago sandbox

Use test cards from the MercadoPago test documentation.

---

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `stripe not configured` | Missing env vars | Set `STRIPE_SECRET_KEY` |
| `Webhook signature invalid` | Wrong secret | Set `STRIPE_WEBHOOK_SECRET` from Dashboard |
| `No such customer` | Stale Stripe customer ID | Re-create customer |
| `Payment method not found` | No card on file | Use billing portal to add card |
