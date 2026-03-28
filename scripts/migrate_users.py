#!/usr/bin/env python3
"""
Migrate existing users between plans or update subscription data.

Usage:
    python scripts/migrate_users.py --dry-run
    python scripts/migrate_users.py --from-plan free --to-plan basic --email-domain empresa.com
    python scripts/migrate_users.py --reset-quotas
    python scripts/migrate_users.py --fix-limits
"""
import argparse
import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PLAN_LIMITS = {
    "free":       {"monthly_call_limit": 50,    "api_requests_per_day": 100},
    "basic":      {"monthly_call_limit": 500,   "api_requests_per_day": 1000},
    "pro":        {"monthly_call_limit": 2000,  "api_requests_per_day": 10000},
    "enterprise": {"monthly_call_limit": -1,    "api_requests_per_day": -1},
}


async def dry_run_report():
    """Print migration report without making changes."""
    print("=" * 60)
    print("  DRY RUN — Migration Report")
    print("=" * 60)
    print(f"  Timestamp: {datetime.utcnow().isoformat()}")

    try:
        from database.models.user import User
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select, func

        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentevoz.db")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

            from collections import Counter
            plan_counts = Counter(u.subscription_plan for u in users)
            print(f"\n  Total users: {len(users)}")
            print("\n  Users by plan:")
            for plan, count in sorted(plan_counts.items()):
                print(f"    {plan:12s}: {count}")

            # Find users with mismatched limits
            mismatched = []
            for u in users:
                plan = str(u.subscription_plan).split(".")[-1].lower()
                expected = PLAN_LIMITS.get(plan, {})
                if expected and u.monthly_call_limit != expected.get("monthly_call_limit"):
                    mismatched.append((u.email, plan, u.monthly_call_limit, expected.get("monthly_call_limit")))

            if mismatched:
                print(f"\n  Users with mismatched limits ({len(mismatched)}):")
                for email, plan, current, expected in mismatched[:10]:
                    print(f"    {email}: {plan} plan, limit={current} (expected {expected})")

        await engine.dispose()

    except ImportError as e:
        print(f"\n  [WARN] Database not available: {e}")
        print("  Would analyze user plans and limits.")

    print("\n  Run without --dry-run to apply changes.")


async def reset_quotas():
    """Reset monthly call counts for all users (run at start of billing cycle)."""
    print("[INFO] Resetting monthly call counts...")
    try:
        from database.models.user import User
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import update

        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentevoz.db")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            await session.execute(update(User).values(monthly_call_count=0))
            await session.commit()
            print("[OK] Monthly call counts reset to 0.")

        await engine.dispose()

    except ImportError as e:
        print(f"[WARN] Database not available: {e}")


async def fix_limits():
    """Fix users whose monthly_call_limit doesn't match their subscription plan."""
    print("[INFO] Fixing user plan limits...")
    fixed = 0
    try:
        from database.models.user import User
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select

        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentevoz.db")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

            for user in users:
                plan = str(user.subscription_plan).split(".")[-1].lower()
                limits = PLAN_LIMITS.get(plan)
                if limits:
                    expected_limit = limits["monthly_call_limit"]
                    if user.monthly_call_limit != expected_limit:
                        user.monthly_call_limit = expected_limit
                        fixed += 1

            await session.commit()
            print(f"[OK] Fixed limits for {fixed} users.")

        await engine.dispose()

    except ImportError as e:
        print(f"[WARN] Database not available: {e}")


async def migrate_plan(from_plan: str, to_plan: str, email_domain: str = None):
    """Migrate users from one plan to another, optionally filtered by email domain."""
    print(f"[INFO] Migrating users: {from_plan} → {to_plan}" + (f" (@{email_domain})" if email_domain else ""))
    try:
        from database.models.user import User, SubscriptionPlan
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select

        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentevoz.db")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        migrated = 0
        async with async_session() as session:
            result = await session.execute(select(User))
            users = result.scalars().all()

            for user in users:
                plan_str = str(user.subscription_plan).split(".")[-1].lower()
                if plan_str != from_plan:
                    continue
                if email_domain and not user.email.endswith("@" + email_domain):
                    continue
                user.subscription_plan = SubscriptionPlan[to_plan.upper()]
                user.monthly_call_limit = PLAN_LIMITS[to_plan]["monthly_call_limit"]
                migrated += 1

            await session.commit()
            print(f"[OK] Migrated {migrated} users from '{from_plan}' to '{to_plan}'.")

        await engine.dispose()

    except ImportError as e:
        print(f"[WARN] Database not available: {e}")


def main():
    parser = argparse.ArgumentParser(description="Migrate AgenteDeVoz users between plans.")
    parser.add_argument("--dry-run",      action="store_true", help="Show report without making changes")
    parser.add_argument("--reset-quotas", action="store_true", help="Reset monthly call counts to 0")
    parser.add_argument("--fix-limits",   action="store_true", help="Fix mismatched plan limits")
    parser.add_argument("--from-plan",    choices=["free","basic","pro","enterprise"], help="Source plan")
    parser.add_argument("--to-plan",      choices=["free","basic","pro","enterprise"], help="Target plan")
    parser.add_argument("--email-domain", default=None, help="Filter by email domain (e.g. empresa.com)")
    args = parser.parse_args()

    if args.dry_run:
        asyncio.run(dry_run_report())
    elif args.reset_quotas:
        asyncio.run(reset_quotas())
    elif args.fix_limits:
        asyncio.run(fix_limits())
    elif args.from_plan and args.to_plan:
        asyncio.run(migrate_plan(args.from_plan, args.to_plan, args.email_domain))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
