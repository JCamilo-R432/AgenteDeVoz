# Database Migrations — AgenteDeVoz

## Overview

AgenteDeVoz uses **Alembic** for database schema migrations with async SQLAlchemy support.

```
migrations/
├── alembic.ini              # Alembic configuration
├── env.py                   # Migration environment (async)
├── script.py.mako           # Template for new migration files
└── versions/
    └── 001_initial_schema.py  # Initial schema migration
```

---

## Quick Start

### 1. Configure database URL

```bash
# Option A: Via environment variable
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/agentevoz"

# Option B: Set individual vars (env.py builds the URL)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=agentevoz
export DB_USER=agentevoz_user
export DB_PASSWORD=yourpassword
```

### 2. Create database

```bash
createdb agentevoz
psql -c "CREATE USER agentevoz_user WITH PASSWORD 'yourpassword';"
psql -c "GRANT ALL ON DATABASE agentevoz TO agentevoz_user;"
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Verify

```bash
alembic current
# → 001_initial (head)
```

---

## Migration Commands

| Command | Description |
|---------|-------------|
| `alembic upgrade head` | Apply all pending migrations |
| `alembic upgrade +1` | Apply next migration only |
| `alembic downgrade -1` | Rollback last migration |
| `alembic downgrade base` | Rollback all migrations |
| `alembic current` | Show current revision |
| `alembic history` | Show migration history |
| `alembic show <rev>` | Show details of a revision |
| `alembic stamp head` | Mark as migrated without running SQL |

---

## Creating New Migrations

### Autogenerate from model changes

```bash
# Edit your SQLAlchemy models in src/models.py
# Then generate migration:
alembic revision --autogenerate -m "add_user_profile_fields"

# Review generated file in migrations/versions/
# Then apply:
alembic upgrade head
```

### Manual migration

```bash
alembic revision -m "custom_data_fix"
# Edit the generated file manually
```

---

## Migration Template

```python
"""Description of changes

Revision ID: abc123def456
Revises: 001_initial
Create Date: 2026-03-24 10:00:00

"""
from alembic import op
import sqlalchemy as sa

revision = "abc123def456"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(512), nullable=True))
    op.create_index("ix_users_avatar_url", "users", ["avatar_url"])


def downgrade() -> None:
    op.drop_index("ix_users_avatar_url", "users")
    op.drop_column("users", "avatar_url")
```

---

## Database Schema (Initial)

### `users`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | Auto-generated UUID |
| email | String(255) UNIQUE | User email |
| hashed_password | String(255) | bcrypt hash |
| full_name | String(255) | Display name |
| is_active | Boolean | Account active |
| is_admin | Boolean | Admin flag |
| plan_id | String(50) | Current plan |
| monthly_call_count | Integer | Current month usage |
| monthly_call_limit | Integer | Plan quota |
| created_at | Timestamp | Account creation |

### `subscriptions`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| user_id | UUID FK → users | |
| plan_id | String(50) | Plan identifier |
| status | String(50) | active/cancelled/trial |
| provider | String(50) | stripe/paypal/mercadopago |
| provider_subscription_id | String | External subscription ID |

### `payments`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| user_id | UUID FK → users | |
| amount_cents | Integer | Amount in cents |
| currency | String(3) | USD/EUR/ARS |
| status | String(50) | pending/succeeded/failed |
| provider | String(50) | Payment provider |

### `licenses`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| user_id | UUID FK → users | |
| key | String(50) UNIQUE | PPPP-RRRR-RRRR-CCCC format |
| plan_id | String(50) | Associated plan |
| is_active | Boolean | Key active |

### `voice_calls`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| user_id | UUID FK → users | |
| message | Text | Input message |
| response | Text | AI response |
| duration_seconds | Float | Call duration |
| status | String(50) | completed/failed |

### `audit_logs`
| Column | Type | Description |
|--------|------|-------------|
| id | BigInt PK | Auto-increment |
| user_id | UUID | Actor (nullable) |
| action | String(100) | Action performed |
| resource_type | String(100) | Resource category |
| ip_address | String(45) | Client IP |

---

## Production Deploy with Migrations

```bash
# Always backup before migrating
./scripts/backup_production.sh pre_migration

# Dry run (generate SQL without applying)
./scripts/migrate_database.sh head --dry-run

# Apply
./scripts/migrate_database.sh head

# Verify
alembic current
```

---

## Rollback

```bash
# Roll back one migration
alembic downgrade -1

# Roll back to specific revision
alembic downgrade 001_initial

# Emergency: roll back all
alembic downgrade base
```

After rollback, restore from backup if data was lost.

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Can't locate revision` | Check `migrations/versions/` files |
| `Target database is not up to date` | Run `alembic upgrade head` |
| `Multiple head revisions` | Run `alembic merge heads` |
| `No such table` | Run `alembic upgrade head` first |
| `asyncpg not installed` | `pip install asyncpg` |
| `Cannot import Base` | Check `src/database.py` and model imports in `env.py` |
