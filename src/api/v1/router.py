"""
APIRouter que agrega todos los sub-routers v1.
Montado en /api/v1 por server.py.
"""

from fastapi import APIRouter

from api.v1.endpoints import orders, customers, analytics
from api.v1.endpoints import monitoring

router = APIRouter()

# Multi-tenancy — must come before order/customer routers
from api.v1.endpoints import tenants
from api.v1.endpoints import monitoring
router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])

# Core — pedidos y clientes
router.include_router(orders.router, prefix="/orders", tags=["orders"])
router.include_router(customers.router, prefix="/customers", tags=["customers"])

# Analytics (incluye /analytics/* paths)
router.include_router(analytics.router)

# Auth cliente (OTP, verificación de identidad)
try:
    from api.v1.endpoints.auth_customer import router as auth_customer_router
    router.include_router(auth_customer_router, prefix="/auth", tags=["customer-auth"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"auth_customer no cargado: {e}")

# Notificaciones
try:
    from api.v1.endpoints.notifications import router as notifications_router
    router.include_router(notifications_router)
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"notifications no cargado: {e}")

# Productos e inventario
try:
    from api.v1.endpoints.products import router as products_router
    router.include_router(products_router, prefix="/products", tags=["products"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"products no cargado: {e}")

# Pagos de pedidos
try:
    from api.v1.endpoints.payments_orders import router as payments_router
    router.include_router(payments_router)
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"payments_orders no cargado: {e}")

# Envíos y logística
try:
    from api.v1.endpoints.shipping import router as shipping_router
    router.include_router(shipping_router, prefix="/shipping", tags=["shipping"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"shipping no cargado: {e}")

# Cupones y descuentos
try:
    from api.v1.endpoints.coupons import router as coupons_router
    router.include_router(coupons_router, prefix="/coupons", tags=["coupons"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"coupons no cargado: {e}")

# Reseñas y calificaciones
try:
    from api.v1.endpoints.reviews import router as reviews_router
    router.include_router(reviews_router, prefix="/reviews", tags=["reviews"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"reviews no cargado: {e}")

# FAQ avanzado
try:
    from api.v1.endpoints.faq import router as faq_router
    router.include_router(faq_router, prefix="/faq", tags=["faq"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"faq no cargado: {e}")

# Fidelidad / Loyalty
try:
    from api.v1.endpoints.loyalty import router as loyalty_router
    router.include_router(loyalty_router, prefix="/loyalty", tags=["loyalty"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"loyalty no cargado: {e}")

# Omnicanalidad
try:
    from api.v1.endpoints.channels import router as channels_router
    router.include_router(channels_router, prefix="/channels", tags=["channels"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"channels no cargado: {e}")

# Workflows
try:
    from api.v1.endpoints.workflows import router as workflows_router
    router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"workflows no cargado: {e}")

# Personalización
try:
    from api.v1.endpoints.personalization import router as personalization_router
    router.include_router(personalization_router, prefix="/personalization", tags=["personalization"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"personalization no cargado: {e}")

# Billing (Stripe)
try:
    from api.v1.endpoints.billing import router as billing_router
    router.include_router(billing_router, prefix="/billing", tags=["billing"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"billing no cargado: {e}")

# Admin dashboard
try:
    from api.v1.endpoints.admin import router as admin_router
    router.include_router(admin_router, prefix="/admin", tags=["admin"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"admin no cargado: {e}")

# White-label branding
try:
    from api.v1.endpoints.branding import router as branding_router
    router.include_router(branding_router, prefix="/branding", tags=["branding"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"branding no cargado: {e}")

# Monitoring (health, metrics, stats, test-alert)
try:
    from api.v1.endpoints.monitoring import router as monitoring_router
    router.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"monitoring no cargado: {e}")

# Health & Metrics (sin prefijo /api/v1 — se monta directo en server.py)
# Ver api/v1/endpoints/health.py

# Mobile SDK
try:
    from api.v1.endpoints.mobile import router as mobile_router
    router.include_router(mobile_router, prefix="/mobile", tags=["mobile"])
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"mobile no cargado: {e}")
