"""
OrdersAnalytics — métricas avanzadas de pedidos, clientes, envíos y satisfacción.
ConversationAnalytics — tracking de conversaciones en memoria.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class OrdersAnalytics:
    """Analítica avanzada de pedidos con queries async."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_orders_summary(self, days: int = 30) -> dict:
        """Resumen completo de pedidos: totales, estados, revenue, tendencia."""
        from models.order import Order

        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=days)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Total pedidos
        total_result = await self.session.execute(select(func.count(Order.id)))
        total_orders = total_result.scalar() or 0

        # Pedidos por estado
        status_result = await self.session.execute(
            select(Order.status, func.count(Order.id)).group_by(Order.status)
        )
        orders_by_status = {row[0]: row[1] for row in status_result.all()}

        # Revenue hoy
        rev_today = await self.session.execute(
            select(func.sum(Order.total_amount)).where(
                Order.created_at >= today_start,
                Order.status.not_in(["cancelled", "refunded"]),
            )
        )
        revenue_today = float(rev_today.scalar() or 0)

        # Revenue mes
        rev_month = await self.session.execute(
            select(func.sum(Order.total_amount)).where(
                Order.created_at >= month_start,
                Order.status.not_in(["cancelled", "refunded"]),
            )
        )
        revenue_month = float(rev_month.scalar() or 0)

        # Promedio valor de pedido
        avg_result = await self.session.execute(
            select(func.avg(Order.total_amount)).where(
                Order.status.not_in(["cancelled", "refunded"])
            )
        )
        avg_order_value = round(float(avg_result.scalar() or 0), 2)

        # Tiempo promedio de entrega
        delivery_result = await self.session.execute(
            select(Order.created_at, Order.delivered_at).where(
                Order.delivered_at.is_not(None),
                Order.created_at.is_not(None),
            ).limit(100)
        )
        delivery_times = []
        for created, delivered in delivery_result.all():
            if created and delivered:
                try:
                    diff_hours = (delivered - created).total_seconds() / 3600
                    delivery_times.append(diff_hours)
                except Exception:
                    pass
        avg_delivery_hours = round(sum(delivery_times) / len(delivery_times), 1) if delivery_times else None

        # Tendencia últimos 7 días
        trend = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count_r = await self.session.execute(
                select(func.count(Order.id), func.sum(Order.total_amount)).where(
                    Order.created_at >= day_start,
                    Order.created_at < day_end,
                )
            )
            row = count_r.one()
            trend.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "count": row[0] or 0,
                "revenue": float(row[1] or 0),
            })

        return {
            "total_orders": total_orders,
            "orders_by_status": orders_by_status,
            "revenue_today": revenue_today,
            "revenue_month": revenue_month,
            "avg_order_value": avg_order_value,
            "avg_delivery_time_hours": avg_delivery_hours,
            "orders_trend_7d": trend,
        }

    async def get_customer_analytics(self) -> dict:
        """Analítica de clientes: nuevos, recurrentes, top clientes."""
        from models.customer import Customer
        from models.order import Order

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_r = await self.session.execute(select(func.count(Customer.id)))
        total_customers = total_r.scalar() or 0

        new_r = await self.session.execute(
            select(func.count(Customer.id)).where(Customer.created_at >= month_start)
        )
        new_customers = new_r.scalar() or 0

        # Clientes con más de 1 pedido = recurrentes
        repeat_r = await self.session.execute(
            select(func.count()).select_from(
                select(Order.customer_id).group_by(Order.customer_id)
                .having(func.count(Order.id) > 1).subquery()
            )
        )
        repeat_customers = repeat_r.scalar() or 0

        # Top 5 clientes por gasto
        top_r = await self.session.execute(
            select(
                Customer.full_name, Customer.phone,
                func.count(Order.id).label("order_count"),
                func.sum(Order.total_amount).label("total_spent"),
            )
            .join(Order, Order.customer_id == Customer.id)
            .group_by(Customer.id, Customer.full_name, Customer.phone)
            .order_by(func.sum(Order.total_amount).desc())
            .limit(5)
        )
        top_customers = [
            {"name": r[0], "phone": r[1], "order_count": r[2], "total_spent": float(r[3] or 0)}
            for r in top_r.all()
        ]

        return {
            "total_customers": total_customers,
            "new_customers_month": new_customers,
            "repeat_customers": repeat_customers,
            "retention_rate": round(repeat_customers / max(total_customers, 1) * 100, 1),
            "top_customers": top_customers,
        }

    async def get_shipping_analytics(self) -> dict:
        """Performance de transportadoras."""
        from models.shipment import Shipment
        from models.order import Order

        carrier_r = await self.session.execute(
            select(Shipment.carrier, func.count(Shipment.id), Shipment.status)
            .group_by(Shipment.carrier, Shipment.status)
        )
        by_carrier: dict = {}
        for carrier, count, status in carrier_r.all():
            if carrier not in by_carrier:
                by_carrier[carrier] = {"total": 0, "delivered": 0}
            by_carrier[carrier]["total"] += count
            if status == "delivered":
                by_carrier[carrier]["delivered"] += count

        total_r = await self.session.execute(select(func.count(Shipment.id)))
        total = total_r.scalar() or 1

        delivered_r = await self.session.execute(
            select(func.count(Shipment.id)).where(Shipment.status == "delivered")
        )
        delivered = delivered_r.scalar() or 0

        return {
            "by_carrier": by_carrier,
            "total_shipments": total,
            "delivered": delivered,
            "on_time_rate": round(delivered / total * 100, 1),
        }

    async def get_revenue_metrics(self, period: str = "month") -> dict:
        """Métricas de revenue con comparación vs período anterior."""
        from models.order import Order

        now = datetime.now(timezone.utc)
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start = start - timedelta(days=1)
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            prev_start = start - timedelta(weeks=1)
        elif period == "year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_start = start.replace(year=start.year - 1)
        else:  # month
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            prev_start = (start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        curr_r = await self.session.execute(
            select(func.sum(Order.total_amount), func.count(Order.id)).where(
                Order.created_at >= start,
                Order.status.not_in(["cancelled", "refunded"]),
            )
        )
        curr = curr_r.one()

        prev_r = await self.session.execute(
            select(func.sum(Order.total_amount), func.count(Order.id)).where(
                Order.created_at >= prev_start,
                Order.created_at < start,
                Order.status.not_in(["cancelled", "refunded"]),
            )
        )
        prev = prev_r.one()

        curr_rev = float(curr[0] or 0)
        prev_rev = float(prev[0] or 0)
        growth = round((curr_rev - prev_rev) / max(prev_rev, 1) * 100, 1)

        return {
            "period": period,
            "revenue": curr_rev,
            "orders": curr[1] or 0,
            "prev_revenue": prev_rev,
            "prev_orders": prev[1] or 0,
            "growth_rate": growth,
        }

    async def get_satisfaction_analytics(self) -> dict:
        """NPS y CSAT desde reseñas."""
        try:
            from services.review_service import ReviewService
            svc = ReviewService(self.session)
            nps = await svc.get_nps_score()
            summary = await svc.get_review_summary()
            return {**nps, **summary}
        except Exception as e:
            logger.warning(f"Error en satisfaction analytics: {e}")
            return {"nps": 0, "avg_rating": 0, "total_reviews": 0}


# ── Conversation Analytics (in-memory) ───────────────────────────────────────

class ConversationAnalytics:
    """Tracking de conversaciones en memoria. Interface Redis-ready."""

    def __init__(self):
        self._conversations: List[dict] = []
        self._intents: List[dict] = []
        self.MAX_SIZE = 10000

    def record_conversation(
        self, session_id: str, intents: List[str], resolved: bool, turns: int, duration_s: int
    ) -> None:
        self._conversations.append({
            "session_id": session_id,
            "intents": intents,
            "resolved": resolved,
            "turns": turns,
            "duration_s": duration_s,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._conversations) > self.MAX_SIZE:
            self._conversations = self._conversations[-self.MAX_SIZE:]

    def record_intent(self, intent: str, session_id: str) -> None:
        self._intents.append({
            "intent": intent,
            "session_id": session_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._intents) > self.MAX_SIZE:
            self._intents = self._intents[-self.MAX_SIZE:]

    def get_stats(self, days: int = 7) -> dict:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        recent = [c for c in self._conversations if c.get("ts", "") >= cutoff]
        if not recent:
            return {"total": 0, "resolved": 0, "resolution_rate": 0,
                    "avg_turns": 0, "avg_duration_s": 0}

        resolved = sum(1 for c in recent if c.get("resolved"))
        avg_turns = round(sum(c.get("turns", 0) for c in recent) / len(recent), 1)
        avg_dur = round(sum(c.get("duration_s", 0) for c in recent) / len(recent), 1)
        return {
            "total": len(recent),
            "resolved": resolved,
            "resolution_rate": round(resolved / len(recent) * 100, 1),
            "avg_turns": avg_turns,
            "avg_duration_s": avg_dur,
        }

    def get_top_intents(self, limit: int = 10) -> List[dict]:
        from collections import Counter
        counts = Counter(i["intent"] for i in self._intents)
        return [{"intent": k, "count": v} for k, v in counts.most_common(limit)]

    def get_resolution_rate(self) -> float:
        if not self._conversations:
            return 0.0
        resolved = sum(1 for c in self._conversations if c.get("resolved"))
        return round(resolved / len(self._conversations) * 100, 1)


# Singleton global
conversation_analytics = ConversationAnalytics()
