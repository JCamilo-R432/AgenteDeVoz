"""
Context variable holding the current tenant_id for a request.

Usage:
    # In middleware:
    token = set_current_tenant_id(tenant_id)
    try:
        await call_next(request)
    finally:
        current_tenant_id_var.reset(token)

    # In service/repository:
    tenant_id = get_current_tenant_id()  # returns str or None
"""

from contextvars import ContextVar
from typing import Optional

# Module-level ContextVar — one per async task/request
current_tenant_id_var: ContextVar[Optional[str]] = ContextVar(
    "current_tenant_id", default=None
)


def set_current_tenant_id(tenant_id: Optional[str]):
    """Set the current tenant_id in the context. Returns a token for reset."""
    return current_tenant_id_var.set(tenant_id)


def get_current_tenant_id() -> Optional[str]:
    """Return the tenant_id bound to the current async task, or None."""
    return current_tenant_id_var.get()


def require_tenant_id() -> str:
    """Return the tenant_id or raise RuntimeError if not set."""
    tid = current_tenant_id_var.get()
    if tid is None:
        raise RuntimeError(
            "No tenant_id in context. "
            "Ensure TenantMiddleware is applied and X-API-Key is provided."
        )
    return tid
