"""
Analytics API — métricas avanzadas de pedidos, clientes, conversaciones y satisfacción.
Todos los endpoints requieren autenticación de admin.
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])


def _get_analytics(db: AsyncSession):
    from analytics.orders_analytics import OrdersAnalytics
    return OrdersAnalytics(db)


@router.get("/analytics/orders", dependencies=[Depends(get_current_admin)])
async def orders_summary(days: int = 30, db: AsyncSession = Depends(get_db)):
    """Resumen de pedidos: totales, estados, revenue, tendencia."""
    return await _get_analytics(db).get_orders_summary(days=days)


@router.get("/analytics/customers", dependencies=[Depends(get_current_admin)])
async def customer_analytics(db: AsyncSession = Depends(get_db)):
    """Analítica de clientes: nuevos, recurrentes, top compradores."""
    return await _get_analytics(db).get_customer_analytics()


@router.get("/analytics/shipping", dependencies=[Depends(get_current_admin)])
async def shipping_analytics(db: AsyncSession = Depends(get_db)):
    """Performance de transportadoras: on-time rate, distribución."""
    return await _get_analytics(db).get_shipping_analytics()


@router.get("/analytics/revenue", dependencies=[Depends(get_current_admin)])
async def revenue_metrics(period: str = "month", db: AsyncSession = Depends(get_db)):
    """Revenue por período con comparación vs período anterior. period: day/week/month/year"""
    return await _get_analytics(db).get_revenue_metrics(period=period)


@router.get("/analytics/conversations", dependencies=[Depends(get_current_admin)])
async def conversation_analytics(days: int = 7):
    """Analítica de conversaciones del agente de voz."""
    from analytics.orders_analytics import conversation_analytics
    stats = conversation_analytics.get_stats(days=days)
    top_intents = conversation_analytics.get_top_intents(limit=10)
    return {
        **stats,
        "top_intents": top_intents,
        "period_days": days,
    }


@router.get("/analytics/satisfaction", dependencies=[Depends(get_current_admin)])
async def satisfaction_analytics(db: AsyncSession = Depends(get_db)):
    """NPS + CSAT + distribución de ratings."""
    return await _get_analytics(db).get_satisfaction_analytics()


@router.get("/analytics/intents", dependencies=[Depends(get_current_admin)])
async def intent_analytics(days: int = 7, limit: int = 10):
    """Top intenciones y tasa de resolución."""
    from analytics.orders_analytics import conversation_analytics
    return {
        "top_intents": conversation_analytics.get_top_intents(limit=limit),
        "resolution_rate": conversation_analytics.get_resolution_rate(),
        "period_days": days,
    }


@router.get("/analytics/dashboard", dependencies=[Depends(get_current_admin)])
async def dashboard_kpis(db: AsyncSession = Depends(get_db)):
    """Todos los KPIs en una sola llamada para el dashboard."""
    analytics = _get_analytics(db)
    from analytics.orders_analytics import conversation_analytics

    orders = await analytics.get_orders_summary(days=30)
    revenue = await analytics.get_revenue_metrics(period="month")
    satisfaction = await analytics.get_satisfaction_analytics()
    conv_stats = conversation_analytics.get_stats(days=7)

    return {
        "orders": {
            "total": orders["total_orders"],
            "by_status": orders["orders_by_status"],
            "revenue_today": orders["revenue_today"],
            "revenue_month": orders["revenue_month"],
            "avg_delivery_hours": orders["avg_delivery_time_hours"],
            "trend_7d": orders["orders_trend_7d"],
        },
        "revenue": {
            "current_month": revenue["revenue"],
            "growth_rate": revenue["growth_rate"],
            "avg_order_value": orders["avg_order_value"],
        },
        "satisfaction": {
            "nps": satisfaction.get("nps", 0),
            "avg_rating": satisfaction.get("avg_rating", 0),
            "total_reviews": satisfaction.get("total_reviews", 0),
        },
        "conversations": {
            "total_7d": conv_stats.get("total", 0),
            "resolution_rate": conv_stats.get("resolution_rate", 0),
            "avg_turns": conv_stats.get("avg_turns", 0),
        },
    }
