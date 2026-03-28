from __future__ import annotations
"""
Loyalty Service — puntos, niveles, canje, referidos, cumpleaños.
"""

import logging
import random
import string
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.loyalty import LoyaltyAccount, LoyaltyTransaction, LoyaltyReward

logger = logging.getLogger(__name__)

# ── Configuración de tiers ─────────────────────────────────────────────────────
TIER_THRESHOLDS = {
    "bronze":   0,
    "silver":   1_000,
    "gold":     5_000,
    "platinum": 10_000,
}

TIER_ORDER = ["bronze", "silver", "gold", "platinum"]

# Puntos ganados por cada 100 COP gastados
POINTS_PER_100_COP = 1

# Valor de redención: 1 punto = N COP
COP_PER_POINT = 10

# Bonos especiales
REFERRAL_BONUS_REFERRER = 500
REFERRAL_BONUS_REFERRED = 250
BIRTHDAY_BONUS_MULTIPLIER = 2.0


@dataclass
class EarnResult:
    points_earned: int
    new_balance: int
    tier_before: str
    tier_after: str
    tier_upgraded: bool
    message: str


@dataclass
class RedeemResult:
    success: bool
    points_redeemed: int
    discount_amount: Decimal
    new_balance: int
    message: str
    error_code: str = ""


class LoyaltyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Cuenta ────────────────────────────────────────────────────────────────

    async def get_account(self, customer_id: str) -> Optional[LoyaltyAccount]:
        result = await self.db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_account(self, customer_id: str) -> LoyaltyAccount:
        account = await self.get_account(customer_id)
        if account:
            return account

        account = LoyaltyAccount(
            customer_id=customer_id,
            referral_code=self._generate_referral_code(),
        )
        self.db.add(account)
        await self.db.commit()
        await self.db.refresh(account)
        logger.info("Cuenta de fidelidad creada para customer %s", customer_id)
        return account

    # ── Ganar puntos ──────────────────────────────────────────────────────────

    async def earn_points_for_purchase(
        self,
        customer_id: str,
        order_amount: Decimal,
        order_id: str,
    ) -> EarnResult:
        account = await self.get_or_create_account(customer_id)
        tier_before = account.tier

        # Calcular puntos base
        base_points = int(order_amount / 100) * POINTS_PER_100_COP
        # Aplicar multiplicador de tier
        points = int(base_points * account.tier_multiplier)
        # Bonus cumpleaños
        if self._is_birthday_month(account):
            points = int(points * BIRTHDAY_BONUS_MULTIPLIER)

        return await self._add_points(
            account=account,
            points=points,
            reason=f"Compra #{order_id[:8]}",
            tx_type="earn",
            order_id=order_id,
        )

    async def add_bonus_points(
        self, customer_id: str, points: int, reason: str
    ) -> EarnResult:
        account = await self.get_or_create_account(customer_id)
        return await self._add_points(account, points, reason, tx_type="bonus")

    async def process_referral(
        self, referrer_code: str, new_customer_id: str
    ) -> tuple[EarnResult, EarnResult]:
        """Procesar referido: bonus al referidor y al nuevo cliente."""
        # Buscar cuenta del referidor
        result = await self.db.execute(
            select(LoyaltyAccount).where(LoyaltyAccount.referral_code == referrer_code)
        )
        referrer_account = result.scalar_one_or_none()
        if not referrer_account:
            raise ValueError(f"Código de referido inválido: {referrer_code}")

        # Marcar al nuevo cliente como referido
        new_account = await self.get_or_create_account(new_customer_id)
        new_account.referred_by = referrer_account.customer_id

        referrer_result = await self._add_points(
            referrer_account, REFERRAL_BONUS_REFERRER, "Bono por referido", "bonus"
        )
        new_result = await self._add_points(
            new_account, REFERRAL_BONUS_REFERRED, "Bono de bienvenida referido", "bonus"
        )
        return referrer_result, new_result

    # ── Canjear puntos ────────────────────────────────────────────────────────

    async def redeem_points(
        self, customer_id: str, points_to_redeem: int
    ) -> RedeemResult:
        account = await self.get_account(customer_id)
        if not account:
            return RedeemResult(
                success=False, points_redeemed=0,
                discount_amount=Decimal("0"), new_balance=0,
                message="Cuenta no encontrada", error_code="not_found",
            )
        if points_to_redeem <= 0:
            return RedeemResult(
                success=False, points_redeemed=0,
                discount_amount=Decimal("0"), new_balance=account.available_points,
                message="Cantidad inválida", error_code="invalid_amount",
            )
        if account.available_points < points_to_redeem:
            return RedeemResult(
                success=False, points_redeemed=0,
                discount_amount=Decimal("0"), new_balance=account.available_points,
                message=f"Puntos insuficientes. Disponibles: {account.available_points}",
                error_code="insufficient_points",
            )

        discount = Decimal(points_to_redeem * COP_PER_POINT)
        account.available_points -= points_to_redeem
        account.redeemed_points += points_to_redeem
        account.updated_at = datetime.utcnow().isoformat()

        tx = LoyaltyTransaction(
            account_id=account.id,
            type="redeem",
            points=-points_to_redeem,
            balance_after=account.available_points,
            reason=f"Canje: {points_to_redeem} pts = ${discount:,.0f} COP",
        )
        self.db.add(tx)
        await self.db.commit()

        return RedeemResult(
            success=True,
            points_redeemed=points_to_redeem,
            discount_amount=discount,
            new_balance=account.available_points,
            message=f"Canjeaste {points_to_redeem} puntos por ${discount:,.0f} COP de descuento.",
        )

    # ── Consultas ─────────────────────────────────────────────────────────────

    async def get_summary(self, customer_id: str) -> dict:
        account = await self.get_account(customer_id)
        if not account:
            return {"error": "Cuenta no encontrada"}
        return {
            "customer_id": customer_id,
            "tier": account.tier,
            "tier_display": account.tier.capitalize(),
            "available_points": account.available_points,
            "total_earned": account.total_points_earned,
            "redeemed": account.redeemed_points,
            "tier_multiplier": account.tier_multiplier,
            "points_to_next_tier": account.points_to_next_tier,
            "referral_code": account.referral_code,
            "redemption_value_cop": account.available_points * COP_PER_POINT,
        }

    async def get_transaction_history(
        self, customer_id: str, limit: int = 20
    ) -> List[dict]:
        account = await self.get_account(customer_id)
        if not account:
            return []
        result = await self.db.execute(
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.account_id == account.id)
            .order_by(LoyaltyTransaction.created_at.desc())
            .limit(limit)
        )
        txs = result.scalars().all()
        return [
            {
                "id": tx.id,
                "type": tx.type,
                "points": tx.points,
                "balance_after": tx.balance_after,
                "reason": tx.reason,
                "date": tx.created_at,
            }
            for tx in txs
        ]

    async def get_tiers_info(self) -> List[dict]:
        return [
            {
                "tier": "bronze",
                "min_points": 0,
                "max_points": 999,
                "multiplier": 1.0,
                "benefits": ["1 punto por cada $100 COP", "Descuentos en fechas especiales"],
            },
            {
                "tier": "silver",
                "min_points": 1_000,
                "max_points": 4_999,
                "multiplier": 1.2,
                "benefits": ["1.2x puntos", "Envío gratis en compras >$100.000", "Acceso anticipado a ofertas"],
            },
            {
                "tier": "gold",
                "min_points": 5_000,
                "max_points": 9_999,
                "multiplier": 1.5,
                "benefits": ["1.5x puntos", "Envío gratis siempre", "Atención prioritaria", "Regalo de cumpleaños"],
            },
            {
                "tier": "platinum",
                "min_points": 10_000,
                "max_points": None,
                "multiplier": 2.0,
                "benefits": ["2x puntos", "Envío express gratis", "Agente dedicado", "Acceso VIP", "2x cumpleaños"],
            },
        ]

    def get_voice_summary(self, summary: dict) -> str:
        """Resumen corto para respuesta de voz."""
        tier = summary.get("tier_display", "Bronze")
        pts = summary.get("available_points", 0)
        val = summary.get("redemption_value_cop", 0)
        to_next = summary.get("points_to_next_tier")
        msg = f"Eres nivel {tier} con {pts} puntos disponibles, equivalentes a ${val:,.0f} COP en descuentos."
        if to_next:
            msg += f" Te faltan {to_next} puntos para el siguiente nivel."
        return msg

    # ── Internos ──────────────────────────────────────────────────────────────

    async def _add_points(
        self,
        account: LoyaltyAccount,
        points: int,
        reason: str,
        tx_type: str,
        order_id: Optional[str] = None,
    ) -> EarnResult:
        tier_before = account.tier
        account.total_points_earned += points
        account.available_points += points
        account.updated_at = datetime.utcnow().isoformat()

        tier_after = self._calculate_tier(account.total_points_earned)
        if tier_after != account.tier:
            account.tier = tier_after
            logger.info(
                "Cliente %s subió de nivel: %s → %s",
                account.customer_id, tier_before, tier_after,
            )

        tx = LoyaltyTransaction(
            account_id=account.id,
            type=tx_type,
            points=points,
            balance_after=account.available_points,
            reason=reason,
            order_id=order_id,
        )
        self.db.add(tx)
        await self.db.commit()

        tier_up = tier_after != tier_before
        msg = f"Ganaste {points} puntos. Total disponible: {account.available_points}."
        if tier_up:
            msg += f" ¡Felicidades! Subiste al nivel {tier_after.capitalize()}."

        return EarnResult(
            points_earned=points,
            new_balance=account.available_points,
            tier_before=tier_before,
            tier_after=tier_after,
            tier_upgraded=tier_up,
            message=msg,
        )

    @staticmethod
    def _calculate_tier(total_points: int) -> str:
        tier = "bronze"
        for t, threshold in TIER_THRESHOLDS.items():
            if total_points >= threshold:
                tier = t
        return tier

    @staticmethod
    def _is_birthday_month(account: LoyaltyAccount) -> bool:
        if not account.birthday_month:
            return False
        return datetime.utcnow().month == account.birthday_month

    @staticmethod
    def _generate_referral_code() -> str:
        chars = string.ascii_uppercase + string.digits
        return "ECO" + "".join(random.choices(chars, k=6))
