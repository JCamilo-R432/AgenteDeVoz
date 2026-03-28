"""
Tests para sistemas avanzados (ítems 11-20):
NLP Pipeline, Omnicanalidad, Loyalty, Workflows, Personalization, Monitoring.
Usa SQLite in-memory para tests con BD.
"""
import asyncio
import os
import sys
import pytest
from decimal import Decimal

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
    from database import engine, Base
    import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


# ── 11. NLP Pipeline ──────────────────────────────────────────────────────────

def test_nlp_pipeline_returns_result():
    from nlp.nlp_pipeline import nlp_pipeline
    result = nlp_pipeline.process("¿Dónde está mi pedido ECO-2026-001234?")
    assert result.intent is not None
    assert result.entities.get("order_number") == "ECO-2026-001234"


def test_nlp_pipeline_eco_order_extraction():
    from nlp.nlp_pipeline import nlp_pipeline
    result = nlp_pipeline.process("Quiero rastrear mi pedido ECO-2026-999999")
    assert result.entities.get("order_number") == "ECO-2026-999999"


def test_nlp_pipeline_detects_sarcasm():
    from nlp.nlp_pipeline import nlp_pipeline
    result = nlp_pipeline.process("Claro que sí, excelente servicio como siempre")
    assert result.is_sarcastic is True


def test_nlp_pipeline_no_sarcasm_normal_text():
    from nlp.nlp_pipeline import nlp_pipeline
    result = nlp_pipeline.process("Hola, ¿pueden ayudarme con mi pedido?")
    assert result.is_sarcastic is False


def test_nlp_pipeline_reference_resolution():
    from nlp.nlp_pipeline import nlp_pipeline
    ctx = {"current_order_number": "ECO-2026-111111"}
    result = nlp_pipeline.process("¿cuándo llega ese pedido?", session_context=ctx)
    assert result.entities.get("order_number") == "ECO-2026-111111"


def test_nlp_pipeline_to_dict():
    from nlp.nlp_pipeline import nlp_pipeline
    result = nlp_pipeline.process("Hola!")
    d = result.to_dict()
    assert "intent" in d
    assert "confidence" in d
    assert "is_sarcastic" in d


# ── 12. Omnicanalidad ─────────────────────────────────────────────────────────

def test_channel_router_lists_channels():
    from channels.channel_router import channel_router
    channels = channel_router.list_channels()
    assert "whatsapp" in channels
    assert "telegram" in channels
    assert "sms" in channels


def test_whatsapp_parse_inbound():
    from channels.whatsapp_channel import WhatsAppChannel
    ch = WhatsAppChannel()
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{"text": {"body": "Hola"}}],
                    "contacts": [{"wa_id": "573160438099"}],
                }
            }]
        }]
    }
    msg = ch.parse_inbound(payload)
    assert msg is not None
    assert msg.text == "Hola"
    assert msg.channel == "whatsapp"


def test_telegram_parse_inbound():
    from channels.telegram_channel import TelegramChannel
    ch = TelegramChannel()
    payload = {"message": {"chat": {"id": 12345}, "text": "Hola"}}
    msg = ch.parse_inbound(payload)
    assert msg is not None
    assert msg.channel == "telegram"
    assert msg.text == "Hola"


def test_sms_parse_inbound():
    from channels.sms_channel import SMSChannel
    ch = SMSChannel()
    payload = {"From": "+573160438099", "Body": "Hola desde SMS"}
    msg = ch.parse_inbound(payload)
    assert msg is not None
    assert msg.phone == "+573160438099"


def test_channel_router_set_preference():
    from channels.channel_router import channel_router, ChannelPreference
    pref = ChannelPreference(customer_id="cust-test", preferred_channel="telegram")
    channel_router.set_preference(pref)
    loaded = channel_router.get_preference("cust-test")
    assert loaded.preferred_channel == "telegram"


@pytest.mark.asyncio
async def test_whatsapp_stub_send():
    from channels.whatsapp_channel import WhatsAppChannel
    from channels.base_channel import OutboundMessage

    ch = WhatsAppChannel()  # sin token = stub
    msg = OutboundMessage(channel="whatsapp", channel_user_id="573160438099", text="Test")
    result = await ch.send(msg)
    assert result.success is True


def test_channel_router_stats():
    from channels.channel_router import channel_router
    stats = channel_router.get_stats()
    assert "registered_channels" in stats
    assert len(stats["registered_channels"]) >= 3


# ── 13. Loyalty ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_loyalty_account_created(db_session):
    from services.loyalty_service import LoyaltyService
    from models.customer import Customer
    import uuid

    customer = Customer(
        id=str(uuid.uuid4()), phone="3160000001",
        full_name="Loyalty Tester",
        created_at=__import__("datetime").datetime.utcnow()
    )
    db_session.add(customer)
    await db_session.flush()

    svc = LoyaltyService(db_session)
    account = await svc.get_or_create_account(customer.id)
    assert account.tier == "bronze"
    assert account.available_points == 0
    assert account.referral_code is not None


@pytest.mark.asyncio
async def test_loyalty_earn_points(db_session):
    from services.loyalty_service import LoyaltyService
    from models.customer import Customer
    import uuid

    customer = Customer(
        id=str(uuid.uuid4()), phone="3160000002",
        full_name="Loyalty Earner",
        created_at=__import__("datetime").datetime.utcnow()
    )
    db_session.add(customer)
    await db_session.flush()

    svc = LoyaltyService(db_session)
    result = await svc.earn_points_for_purchase(customer.id, Decimal("50000"), "ord-001")
    assert result.points_earned == 500  # 50000/100 * 1pt
    assert result.new_balance == 500


@pytest.mark.asyncio
async def test_loyalty_tier_upgrade(db_session):
    from services.loyalty_service import LoyaltyService
    from models.customer import Customer
    import uuid

    customer = Customer(
        id=str(uuid.uuid4()), phone="3160000003",
        full_name="Tier Upgrader",
        created_at=__import__("datetime").datetime.utcnow()
    )
    db_session.add(customer)
    await db_session.flush()

    svc = LoyaltyService(db_session)
    # 1000 pts → Silver
    result = await svc.earn_points_for_purchase(customer.id, Decimal("100000"), "ord-002")
    assert result.points_earned == 1000
    assert result.tier_after == "silver"
    assert result.tier_upgraded is True


@pytest.mark.asyncio
async def test_loyalty_redeem_points(db_session):
    from services.loyalty_service import LoyaltyService
    from models.customer import Customer
    import uuid

    customer = Customer(
        id=str(uuid.uuid4()), phone="3160000004",
        full_name="Loyalty Redeemer",
        created_at=__import__("datetime").datetime.utcnow()
    )
    db_session.add(customer)
    await db_session.flush()

    svc = LoyaltyService(db_session)
    await svc.earn_points_for_purchase(customer.id, Decimal("200000"), "ord-003")

    result = await svc.redeem_points(customer.id, 500)
    assert result.success is True
    assert result.discount_amount == Decimal("5000")
    assert result.points_redeemed == 500


@pytest.mark.asyncio
async def test_loyalty_redeem_insufficient_points(db_session):
    from services.loyalty_service import LoyaltyService
    from models.customer import Customer
    import uuid

    customer = Customer(
        id=str(uuid.uuid4()), phone="3160000005",
        full_name="No Points",
        created_at=__import__("datetime").datetime.utcnow()
    )
    db_session.add(customer)
    await db_session.flush()

    svc = LoyaltyService(db_session)
    await svc.get_or_create_account(customer.id)

    result = await svc.redeem_points(customer.id, 9999)
    assert result.success is False
    assert result.error_code == "insufficient_points"


@pytest.mark.asyncio
async def test_loyalty_get_tiers_info(db_session):
    from services.loyalty_service import LoyaltyService
    svc = LoyaltyService(None)
    tiers = await svc.get_tiers_info()
    assert len(tiers) == 4
    tier_names = [t["tier"] for t in tiers]
    assert "bronze" in tier_names
    assert "platinum" in tier_names


def test_loyalty_tier_calculation():
    from services.loyalty_service import LoyaltyService
    assert LoyaltyService._calculate_tier(0) == "bronze"
    assert LoyaltyService._calculate_tier(999) == "bronze"
    assert LoyaltyService._calculate_tier(1000) == "silver"
    assert LoyaltyService._calculate_tier(5000) == "gold"
    assert LoyaltyService._calculate_tier(10000) == "platinum"


# ── 14. Workflows ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_return_workflow_registered():
    from workflows.workflow_engine import workflow_engine
    import workflows.return_workflow  # noqa
    assert "return_order" in workflow_engine._definitions
    assert "custom_order" in workflow_engine._definitions


@pytest.mark.asyncio
async def test_return_workflow_happy_path():
    from workflows.workflow_engine import workflow_engine
    from datetime import datetime, timedelta

    instance = await workflow_engine.start("return_order", {
        "order_id": "ord-ret-001",
        "order_number": "ECO-2026-001234",
        "order_status": "delivered",
        "order_date": (datetime.utcnow() - timedelta(days=5)).isoformat(),
        "order_total": 50000,
        "customer_id": "cust-ret-001",
    })
    # Debe pausar en "confirm_receipt" (requires_human_approval)
    assert instance.status.value in ("waiting", "completed")


@pytest.mark.asyncio
async def test_workflow_invalid_id():
    from workflows.workflow_engine import workflow_engine
    with pytest.raises(ValueError):
        await workflow_engine.start("nonexistent_workflow", {})


@pytest.mark.asyncio
async def test_return_workflow_ineligible():
    from workflows.workflow_engine import workflow_engine

    instance = await workflow_engine.start("return_order", {
        "order_id": "ord-ret-002",
        "order_status": "pending",  # no entregado → debe fallar
        "customer_id": "cust-ret-002",
    })
    assert instance.status.value == "failed"


def test_workflow_engine_cancel():
    import asyncio
    from workflows.workflow_engine import workflow_engine
    # Crear instancia ficticia para cancelar
    from workflows.workflow_engine import WorkflowInstance, WorkflowStatus
    inst = WorkflowInstance(
        instance_id="test-cancel-001",
        workflow_id="return_order",
        status=WorkflowStatus.WAITING,
        context={},
    )
    workflow_engine._instances["test-cancel-001"] = inst
    result = workflow_engine.cancel("test-cancel-001")
    assert result is True
    assert workflow_engine._instances["test-cancel-001"].status == WorkflowStatus.CANCELLED


# ── 16. Personalization ───────────────────────────────────────────────────────

def test_personalization_default_preferences():
    from services.personalization_service import personalization_service
    pref = personalization_service.get_preferences("ptest-001")
    assert pref.preferred_tone in ("formal", "casual")
    assert pref.speech_rate == 1.0


def test_personalization_update_preferences():
    from services.personalization_service import personalization_service
    pref = personalization_service.update_preferences("ptest-002", {"preferred_tone": "formal"})
    assert pref.preferred_tone == "formal"


def test_personalization_greeting_casual():
    from services.personalization_service import personalization_service
    personalization_service.update_preferences("ptest-003", {"preferred_tone": "casual"})
    greeting = personalization_service.get_personalized_greeting("ptest-003", "Juan Pérez", 3)
    assert "Juan" in greeting


def test_personalization_greeting_formal():
    from services.personalization_service import personalization_service
    personalization_service.update_preferences("ptest-004", {"preferred_tone": "formal"})
    greeting = personalization_service.get_personalized_greeting("ptest-004", "María García")
    assert "María" in greeting


def test_personalization_tts_config():
    from services.personalization_service import personalization_service
    config = personalization_service.get_tts_config("ptest-001")
    assert "rate" in config
    assert "language" in config


def test_personalization_recommendations_cold_start():
    from services.personalization_service import personalization_service
    # Sin historial → trending
    personalization_service.update_trending(["SKU-001", "SKU-002", "SKU-003"])
    result = personalization_service.get_recommendations("newcust-cold", limit=3)
    assert result.strategy == "trending"


def test_personalization_recommendations_repurchase():
    from services.personalization_service import personalization_service
    # Historial con compra repetida
    for _ in range(3):
        personalization_service.record_purchase("ptest-rep", "SKU-REPEAT", "electronics")
    result = personalization_service.get_recommendations("ptest-rep")
    assert result.strategy == "repurchase"
    assert "SKU-REPEAT" in result.product_ids


def test_personalization_voice_recommendation():
    from services.personalization_service import personalization_service
    personalization_service.update_trending(["SKU-T1"])
    msg = personalization_service.get_voice_recommendation("no-history-cust")
    assert isinstance(msg, str)
    assert len(msg) > 0


# ── 19. Monitoring ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_checker_liveness():
    from monitoring.health_checks import health_checker
    assert await health_checker.is_alive() is True


@pytest.mark.asyncio
async def test_health_full_report():
    from monitoring.health_checks import health_checker
    report = await health_checker.run_all()
    assert report.status in ("healthy", "degraded", "unhealthy")
    assert len(report.components) > 0
    assert report.uptime_seconds > 0


def test_metrics_counter_increment():
    from monitoring.metrics import registry
    c = registry.counter("test_counter_001", "Test counter", ["label"])
    c.inc(1.0, label="a")
    c.inc(2.0, label="a")
    assert c.get(label="a") == 3.0


def test_metrics_gauge_set():
    from monitoring.metrics import registry
    g = registry.gauge("test_gauge_001", "Test gauge")
    g.set(42.0)
    assert g.get() == 42.0


def test_metrics_prometheus_text_format():
    from monitoring.metrics import registry
    text = registry.to_prometheus_text()
    assert "# HELP" in text
    assert "# TYPE" in text


def test_global_metrics_counters_exist():
    from monitoring.metrics import (
        conversations_total, escalations_total,
        orders_processed, active_sessions,
    )
    conversations_total.inc(1.0, channel="web")
    escalations_total.inc(1.0, reason="frustration")
    active_sessions.set(5.0)
    assert conversations_total.get(channel="web") >= 1.0
    assert active_sessions.get() == 5.0
