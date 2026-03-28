from __future__ import annotations
"""
user_repository.py — Async SQLAlchemy repository for the users table.
"""


import logging
from typing import List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class UserRepository:
    """CRUD operations for the User ORM model."""

    def __init__(self, db_session):
        self._db = db_session

    async def get_by_id(self, user_id: str) -> Optional[object]:
        from database.models.user import User
        result = await self._db.get(User, UUID(user_id))
        return result

    async def get_by_email(self, email: str) -> Optional[object]:
        from database.models.user import User
        from sqlalchemy import select
        stmt   = select(User).where(User.email == email.lower())
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_license_key(self, key: str) -> Optional[object]:
        from database.models.user import User
        from sqlalchemy import select
        stmt   = select(User).where(User.license_key == key)
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, **kwargs) -> object:
        from database.models.user import User
        user = User(**kwargs)
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        logger.info("User created: %s", user.email)
        return user

    async def update(self, user_id: str, **kwargs) -> Optional[object]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        for key, val in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, val)
        await self._db.flush()
        return user

    async def delete(self, user_id: str) -> bool:
        user = await self.get_by_id(user_id)
        if not user:
            return False
        await self._db.delete(user)
        await self._db.flush()
        return True

    async def list_all(self, offset: int = 0, limit: int = 50) -> List[object]:
        from database.models.user import User
        from sqlalchemy import select
        stmt   = select(User).offset(offset).limit(limit).order_by(User.created_at.desc())
        result = await self._db.execute(stmt)
        return result.scalars().all()

    async def count(self) -> int:
        from database.models.user import User
        from sqlalchemy import func, select
        result = await self._db.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def email_exists(self, email: str) -> bool:
        return (await self.get_by_email(email)) is not None
