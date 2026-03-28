"""
Tests de los nuevos sistemas: Productos, Pagos, Cupones, Reseñas, FAQ, Envíos.
Usa SQLite in-memory.
"""
import asyncio
import os
import sys
import pytest

_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_session():
    """Sesión de BD con tablas creadas."""
    from database import engine, Base
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


# ── FAQ Tests ─────────────────────────────────────────────────────────────────

def test_faq_search_returns_results():
    from knowledge.faq_advanced import AdvancedFAQManager
    faq = AdvancedFAQManager()
    results = faq.search("cuánto demora la entrega")
    assert len(results) > 0


def test_faq_answer_for_tracking_query():
    from knowledge.faq_advanced import AdvancedFAQManager
    faq = AdvancedFAQManager()
    answer = faq.answer("cómo rastreo mi pedido")
    assert "rastrear" in answer.lower() or "guía" in answer.lower() or "tracking" in answer.lower()


def test_faq_no_results_for_gibberish():
    from knowledge.faq_advanced import AdvancedFAQManager
    faq = AdvancedFAQManager()
    results = faq.search("xyzabc123 qwerty")
    assert len(results) == 0


def test_faq_suggestions_prefix_match():
    from knowledge.faq_advanced import AdvancedFAQManager
    faq = AdvancedFAQManager()
    suggestions = faq.get_suggestions("¿Cómo")
    assert len(suggestions) > 0


def test_faq_voice_answer_is_short():
    from knowledge.faq_advanced import AdvancedFAQManager
    faq = AdvancedFAQManager()
    answer = faq.get_voice_answer("cuánto demora la entrega")
    # Max 2 oraciones = no demasiado largo
    assert len(answer) < 500


def test_faq_custom_entry_added():
    from knowledge.faq_advanced import AdvancedFAQManager, FAQEntry
    faq = AdvancedFAQManager()
    entry = FAQEntry("custom-1", "test", "¿Test?", "Respuesta test.", ["test", "prueba"])
    faq.add_custom_entry(entry)
    results = faq.search("prueba test")
    assert any(r.entry.id == "custom-1" for r in results)


def test_faq_categories():
    from knowledge.faq_advanced import AdvancedFAQManager
    faq = AdvancedFAQManager()
    cats = faq.get_categories()
    assert "pedidos" in cats
    assert "pagos" in cats


# ── Shipping Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_coordinadora_generates_tracking_number():
    from services.shipping_integration import CoordinadoraIntegration
    carrier = CoordinadoraIntegration()
    order_mock = type("O", (), {"order_number": "ECO-2026-001"})()
    info = await carrier.create_shipment(order_mock, {})
    assert info.tracking_number.startswith("COR")
    assert info.carrier == "Coordinadora"


@pytest.mark.asyncio
async def test_tracking_number_auto_detect_carrier():
    from services.shipping_integration import ShippingIntegration
    shipping = ShippingIntegration()
    info = await shipping.get_tracking_status("SRV123456COL")
    assert info.carrier == "Servientrega"


@pytest.mark.asyncio
async def test_calculate_rate_returns_options():
    from services.shipping_integration import ShippingIntegration
    shipping = ShippingIntegration()
    rates = await shipping.calculate_rate("Bogotá", "Medellín", 1.0)
    assert len(rates) > 0
    assert all("price" in r for r in rates)
    assert all(r["price"] > 0 for r in rates)


def test_format_tracking_for_voice():
    from services.shipping_integration import ShippingIntegration, TrackingInfo
    from datetime import datetime, timezone
    shipping = ShippingIntegration()
    info = TrackingInfo(
        tracking_number="COR123456COL",
        carrier="Coordinadora",
        status="in_transit",
        current_location="Bogotá",
        estimated_delivery=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    voice = shipping.format_tracking_for_voice(info)
    assert "tránsito" in voice or "camino" in voice


# ── Coupon Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_coupon_percentage_calculation(db_session):
    from services.coupon_service import CouponService
    from decimal import Decimal
    from models.coupon import Coupon
    import uuid

    coupon = Coupon(
        id=str(uuid.uuid4()), code="TEST10", name="10% off",
        type="percentage", value=Decimal("10"),
        valid_from="2026-01-01T00:00:00", is_active=True,
        usage_limit_per_customer=10,
    )
    db_session.add(coupon)
    await db_session.commit()

    svc = CouponService(db_session)
    discount = svc.calculate_discount(coupon, Decimal("100000"))
    assert discount == Decimal("10000.00")


@pytest.mark.asyncio
async def test_coupon_fixed_amount_calculation(db_session):
    from services.coupon_service import CouponService
    from decimal import Decimal
    from models.coupon import Coupon
    import uuid

    coupon = Coupon(
        id=str(uuid.uuid4()), code="FIJO5K", name="$5000 off",
        type="fixed_amount", value=Decimal("5000"),
        valid_from="2026-01-01T00:00:00", is_active=True,
        usage_limit_per_customer=10,
    )
    db_session.add(coupon)
    await db_session.commit()

    svc = CouponService(db_session)
    discount = svc.calculate_discount(coupon, Decimal("50000"))
    assert discount == Decimal("5000")


@pytest.mark.asyncio
async def test_coupon_not_found(db_session):
    from services.coupon_service import CouponService
    from decimal import Decimal
    svc = CouponService(db_session)
    result = await svc.validate_coupon("NOEXISTE", "cust-1", Decimal("50000"))
    assert result.valid is False
    assert result.error_code == "not_found"


@pytest.mark.asyncio
async def test_coupon_min_purchase_not_met(db_session):
    from services.coupon_service import CouponService
    from decimal import Decimal
    from models.coupon import Coupon
    import uuid

    coupon = Coupon(
        id=str(uuid.uuid4()), code="MINPURCH", name="Min purchase test",
        type="fixed_amount", value=Decimal("10000"),
        min_purchase_amount=Decimal("100000"),
        valid_from="2026-01-01T00:00:00", is_active=True,
        usage_limit_per_customer=5,
    )
    db_session.add(coupon)
    await db_session.commit()

    svc = CouponService(db_session)
    result = await svc.validate_coupon("MINPURCH", "cust-1", Decimal("50000"))
    assert result.valid is False
    assert result.error_code == "min_purchase"


# ── Review Tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_review_creates_record(db_session):
    from services.review_service import ReviewService
    import uuid

    svc = ReviewService(db_session)

    # Crear datos mínimos requeridos
    from models.customer import Customer
    from models.order import Order
    from decimal import Decimal

    customer = Customer(
        id=str(uuid.uuid4()), phone="3160438099",
        full_name="Test Reviewer", created_at=__import__("datetime").datetime.utcnow()
    )
    db_session.add(customer)
    await db_session.flush()

    order = Order(
        id=str(uuid.uuid4()), order_number="ECO-2026-REV001",
        customer_id=customer.id, status="delivered",
        total_amount=Decimal("50000"),
    )
    db_session.add(order)
    await db_session.commit()

    review = await svc.submit_review(
        order_id=order.id, customer_id=customer.id,
        rating=5, body="Excelente producto, llegó rápido y en perfecto estado.",
    )
    assert review.rating == 5
    assert review.sentiment == "positive"


def test_review_sentiment_positive():
    from services.review_service import ReviewService
    svc = ReviewService(None)
    assert svc._detect_sentiment("excelente servicio, muy satisfecho") == "positive"


def test_review_sentiment_negative():
    from services.review_service import ReviewService
    svc = ReviewService(None)
    assert svc._detect_sentiment("terrible experiencia, muy malo y lento") == "negative"


def test_review_sentiment_neutral():
    from services.review_service import ReviewService
    svc = ReviewService(None)
    assert svc._detect_sentiment("llegó el pedido") == "neutral"


@pytest.mark.asyncio
async def test_nps_score_empty_db(db_session):
    from services.review_service import ReviewService
    svc = ReviewService(db_session)
    nps = await svc.get_nps_score()
    assert "nps" in nps
    assert nps["total"] >= 0
