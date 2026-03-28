# Landing Page Guide — AgenteDeVoz

## Overview

The landing page system consists of:

| Layer | Files | Purpose |
|-------|-------|---------|
| Static HTML | `public/index.html`, `public/agent.html` | Zero-dependency fallback (no server needed) |
| CSS | `public/css/styles.css` | Custom animations, gradients, components |
| JS | `public/js/main.js`, `voice-agent.js`, `chatwoot-integration.js` | Interactivity |
| SVG | `public/images/logo.svg`, `hero-illustration.svg` | Vector assets |
| Jinja2 | `templates/` + `templates/components/` | SSR via FastAPI |
| Python | `src/web/landing_routes.py`, `src/web/voice_interface.py` | API + route handlers |
| Config | `config/chatwoot_config.py` | Chatwoot credentials |

---

## Quick Start (Static)

Open `public/index.html` directly in a browser — no server required.
The voice agent at `public/agent.html` requires the FastAPI backend for `/api/v1/voice/process`.

---

## Quick Start (FastAPI)

```bash
# 1. Install deps (if not already done)
pip install fastapi uvicorn jinja2 aiofiles

# 2. Mount web routers in your server
# In src/server.py:
from src.web import landing_router, voice_router
app.include_router(landing_router)
app.include_router(voice_router)

# 3. Serve static files
from fastapi.staticfiles import StaticFiles
app.mount("/css",    StaticFiles(directory="public/css"),    name="css")
app.mount("/js",     StaticFiles(directory="public/js"),     name="js")
app.mount("/images", StaticFiles(directory="public/images"), name="images")

# 4. Run
uvicorn src.server:app --reload --port 8000
```

Then visit:
- `http://localhost:8000/` — landing page
- `http://localhost:8000/agent` — voice agent demo

---

## Chatwoot Configuration

### 1. Create a Chatwoot account and website inbox

1. Log in to your Chatwoot instance.
2. Go to **Settings → Inboxes → New Inbox → Website**.
3. Copy the **Website Token**.

### 2. Set environment variables

```bash
export CHATWOOT_BASE_URL="https://chat.yourdomain.com"
export CHATWOOT_TOKEN="your_website_token_here"
```

Or add to `config/production.env`:

```env
CHATWOOT_BASE_URL=https://chat.yourdomain.com
CHATWOOT_TOKEN=your_website_token_here
```

### 3. Verify

```python
from config.chatwoot_config import ChatwootConfig
print(ChatwootConfig.is_configured())  # → True
```

---

## Voice Agent API

The browser calls `POST /api/v1/voice/process` with:

```json
{
  "session_id": "sess_abc123_xyz",
  "text": "¿Cuáles son los planes de precio?",
  "language": "es-CO",
  "channel": "web",
  "metadata": { "source": "landing_page" }
}
```

Response:

```json
{
  "session_id": "sess_abc123_xyz",
  "response": "Tenemos tres planes: Gratis, Pro y Enterprise…",
  "language": "es-CO",
  "intent": "faq",
  "confidence": 0.92,
  "escalate": false,
  "timestamp": "2026-03-23T12:00:00"
}
```

When the full VoiceAgent pipeline is not running, `voice_interface.py` falls back
to scripted demo responses so the page remains interactive.

---

## Customisation

### Brand colors

Edit the Tailwind config at the top of each HTML file:

```js
tailwind.config = {
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: '#4f46e5', dark: '#3730a3' }
      }
    }
  }
}
```

Also update `--color-*` CSS variables in `public/css/styles.css` if you change gradients.

### FAQ content

FAQ items are defined as a JS array in `public/js/main.js` → `initFAQ()`.
Edit the `faqs` array to add, remove, or update questions.

### Pricing plans

Edit `templates/components/pricing.html` (SSR) or the pricing section in `public/index.html` (static).

---

## Deployment (nginx)

See `scripts/deploy_landing.sh` for automated setup, or configure nginx manually:

```nginx
server {
    listen 443 ssl http2;
    server_name agentevoz.com www.agentevoz.com;

    # Static assets (served directly by nginx, bypassing FastAPI)
    location /css/    { root /var/www/agentevoz/public; expires 30d; }
    location /js/     { root /var/www/agentevoz/public; expires 30d; }
    location /images/ { root /var/www/agentevoz/public; expires 30d; }

    # Everything else → FastAPI
    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
    }
}
```

---

## SEO Checklist

- [x] `<title>` and `<meta name="description">` set per page
- [x] Open Graph and Twitter Card meta tags
- [x] `<link rel="canonical">` on every page
- [x] Semantic HTML5 landmarks (`<header>`, `<main>`, `<footer>`, `<nav>`, `<section>`)
- [x] `aria-label` and `role` attributes for accessibility
- [x] `preconnect` for Google Fonts and CDN
- [ ] `sitemap.xml` — create and submit to Google Search Console
- [ ] `robots.txt` — ensure `Disallow` only for `/api/` and `/dashboard/`
- [ ] Core Web Vitals — run Lighthouse; target LCP < 2.5 s, CLS < 0.1
