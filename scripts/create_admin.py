#!/usr/bin/env python3
"""
Create or promote a user to admin role.

Usage:
    python scripts/create_admin.py --email admin@example.com --password Admin1234! --name "Admin User"
    python scripts/create_admin.py --email existing@example.com --promote-only
"""
import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def create_admin(email: str, password: str, full_name: str) -> None:
    """Create a new admin user in the database."""
    try:
        from database.models.user import User, SubscriptionPlan
        from src.auth.password_hashing import PasswordHasher
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select
        import uuid

        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentevoz.db")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        hasher = PasswordHasher()
        valid, msg = hasher.validate_strength(password) if isinstance(hasher.validate_strength(password), tuple) else (hasher.validate_strength(password), "")
        if not valid:
            print(f"[ERROR] Password too weak: {msg}")
            sys.exit(1)

        hashed = hasher.hash_password(password)

        async with async_session() as session:
            # Check if user already exists
            result = await session.execute(select(User).where(User.email == email))
            existing = result.scalar_one_or_none()

            if existing:
                existing.is_admin = True
                existing.is_active = True
                await session.commit()
                print(f"[OK] User '{email}' promoted to admin.")
            else:
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    hashed_password=hashed,
                    full_name=full_name,
                    is_admin=True,
                    is_active=True,
                    subscription_plan=SubscriptionPlan.ENTERPRISE,
                    monthly_call_limit=-1,
                )
                session.add(user)
                await session.commit()
                print(f"[OK] Admin user created: {email}")

        await engine.dispose()

    except ImportError as e:
        print(f"[WARN] Could not connect to database ({e}). Creating admin in demo mode.")
        print(f"[INFO] Would create admin: {email} / {full_name}")


async def promote_only(email: str) -> None:
    """Promote an existing user to admin without changing their password."""
    try:
        from database.models.user import User
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import select

        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./agentevoz.db")
        engine = create_async_engine(DATABASE_URL, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                print(f"[ERROR] User '{email}' not found.")
                sys.exit(1)
            user.is_admin = True
            await session.commit()
            print(f"[OK] User '{email}' promoted to admin.")

        await engine.dispose()

    except ImportError as e:
        print(f"[WARN] Database not available: {e}")


def main():
    parser = argparse.ArgumentParser(description="Create or promote admin users in AgenteDeVoz.")
    parser.add_argument("--email",        required=True, help="Admin email address")
    parser.add_argument("--password",     default=None,  help="Admin password (min 8 chars, 1 uppercase, 1 digit)")
    parser.add_argument("--name",         default="Admin", help="Full name")
    parser.add_argument("--promote-only", action="store_true", help="Only promote existing user, don't create new")
    args = parser.parse_args()

    if args.promote_only:
        asyncio.run(promote_only(args.email))
    else:
        if not args.password:
            print("[ERROR] --password is required when creating a new admin.")
            sys.exit(1)
        asyncio.run(create_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
