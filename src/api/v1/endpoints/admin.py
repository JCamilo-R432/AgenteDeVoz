from __future__ import annotations
"""
Admin API endpoints — Module 6.
All routes require X-Admin-Secret header (set ADMIN_SECRET env var).

GET  /api/v1/admin/stats                   — platform-wide stats
GET  /api/v1/admin/tenants                 — paginated tenant list
GET  /api/v1/admin/tenants/{id}            — tenant detail + usage
PATCH /api/v1/admin/tenants/{id}/plan      — change tenant plan
PATCH /api/v1/admin/tenants/{id}/status    — activate/deactivate tenant
GET  /api/v1/admin/auth-events             — recent auth audit log
GET  /api/v1/admin/dashboard               — HTML dashboard page
"""


import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from services.admin_service import AdminService

router = APIRouter(tags=["admin"])


# ── Auth guard ─────────────────────────────────────────────────────────────────

def _admin_guard(request: Request) -> None:
    secret = request.headers.get("X-Admin-Secret", "")
    expected = os.getenv("ADMIN_SECRET", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_SECRET not configured on this server",
        )
    if secret != expected:
        raise HTTPException(status_code=403, detail="Invalid admin secret")


# ── Stats ──────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def platform_stats(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _admin_guard(request)
    svc = AdminService(db)
    return await svc.get_platform_stats()


# ── Tenant list ────────────────────────────────────────────────────────────────

@router.get("/tenants")
async def list_tenants(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    plan: Optional[str] = None,
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _admin_guard(request)
    svc = AdminService(db)
    return await svc.list_tenants(page=page, page_size=page_size, plan=plan, active_only=active_only)


# ── Tenant detail ──────────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}")
async def tenant_detail(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _admin_guard(request)
    svc = AdminService(db)
    return await svc.get_tenant_detail(tenant_id)


# ── Update plan ────────────────────────────────────────────────────────────────

class PlanUpdate(BaseModel):
    plan: str


@router.patch("/tenants/{tenant_id}/plan")
async def update_tenant_plan(
    tenant_id: str,
    body: PlanUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _admin_guard(request)

    valid_plans = {"basic", "pro", "enterprise"}
    if body.plan not in valid_plans:
        raise HTTPException(status_code=400, detail=f"Plan must be one of {valid_plans}")

    from sqlalchemy import select
    from models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.plan = body.plan
    await db.flush()
    return {"id": tenant_id, "plan": tenant.plan, "updated": True}


# ── Update status ──────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    is_active: bool


@router.patch("/tenants/{tenant_id}/status")
async def update_tenant_status(
    tenant_id: str,
    body: StatusUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _admin_guard(request)

    from sqlalchemy import select
    from models.tenant import Tenant

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant.is_active = body.is_active
    await db.flush()
    return {"id": tenant_id, "is_active": tenant.is_active, "updated": True}


# ── Auth events ────────────────────────────────────────────────────────────────

@router.get("/auth-events")
async def auth_events(
    request: Request,
    tenant_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> list:
    _admin_guard(request)
    svc = AdminService(db)
    return await svc.recent_auth_events(tenant_id=tenant_id, limit=limit)


# ── HTML Dashboard ─────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request) -> HTMLResponse:
    """
    Serve the admin dashboard HTML page.
    The page authenticates via X-Admin-Secret stored in localStorage
    and fetches data from the JSON endpoints above.
    """
    _admin_guard(request)
    html = _render_dashboard_html()
    return HTMLResponse(content=html)


def _render_dashboard_html() -> str:
    return """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AgenteDeVoz — Admin Dashboard</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
<style>
  body { background:#f0f2f5; }
  .sidebar { width:240px; min-height:100vh; background:#1e293b; color:#cbd5e1; }
  .sidebar .nav-link { color:#94a3b8; }
  .sidebar .nav-link.active, .sidebar .nav-link:hover { color:#fff; background:rgba(255,255,255,.08); border-radius:8px; }
  .sidebar .brand { font-size:1.1rem; font-weight:700; color:#fff; padding:1.5rem 1rem 1rem; }
  .card-stat { border:none; border-radius:16px; box-shadow:0 2px 8px rgba(0,0,0,.06); }
  .stat-icon { width:48px; height:48px; border-radius:12px; display:flex; align-items:center; justify-content:center; font-size:1.3rem; }
  .table-container { border-radius:16px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.06); }
  #secret-modal { display:none; position:fixed; inset:0; background:rgba(0,0,0,.5); z-index:9999; align-items:center; justify-content:center; }
  #secret-modal.show { display:flex; }
</style>
</head>
<body>

<!-- Secret modal -->
<div id="secret-modal" class="show">
  <div class="bg-white rounded-4 p-4 shadow" style="width:360px">
    <h5 class="mb-3"><i class="fas fa-lock text-primary me-2"></i>Admin Access</h5>
    <input id="secret-input" type="password" class="form-control mb-3" placeholder="ADMIN_SECRET">
    <button class="btn btn-primary w-100" onclick="saveSecret()">Ingresar</button>
  </div>
</div>

<div class="d-flex" id="main-layout" style="display:none!important">
  <!-- Sidebar -->
  <div class="sidebar d-flex flex-column p-2">
    <div class="brand"><i class="fas fa-microphone-alt me-2"></i>AgenteDeVoz</div>
    <nav class="nav flex-column gap-1 mt-2">
      <a href="#" class="nav-link active px-3 py-2" onclick="showSection('overview')">
        <i class="fas fa-chart-pie me-2"></i>Overview
      </a>
      <a href="#" class="nav-link px-3 py-2" onclick="showSection('tenants')">
        <i class="fas fa-building me-2"></i>Tenants
      </a>
      <a href="#" class="nav-link px-3 py-2" onclick="showSection('auth-events')">
        <i class="fas fa-shield-alt me-2"></i>Auth Events
      </a>
    </nav>
    <div class="mt-auto p-3 text-xs text-secondary">
      <button class="btn btn-sm btn-outline-secondary w-100" onclick="logout()">
        <i class="fas fa-sign-out-alt me-1"></i>Cerrar sesión
      </button>
    </div>
  </div>

  <!-- Content -->
  <div class="flex-grow-1 p-4">

    <!-- Overview -->
    <section id="section-overview">
      <h4 class="fw-bold mb-4">Platform Overview</h4>
      <div class="row g-3 mb-4" id="stats-cards">
        <div class="col-sm-6 col-xl-3">
          <div class="card card-stat p-4">
            <div class="d-flex align-items-center gap-3">
              <div class="stat-icon bg-primary bg-opacity-10 text-primary"><i class="fas fa-building"></i></div>
              <div><div class="text-secondary small">Tenants activos</div><div class="fs-4 fw-bold" id="stat-tenants">—</div></div>
            </div>
          </div>
        </div>
        <div class="col-sm-6 col-xl-3">
          <div class="card card-stat p-4">
            <div class="d-flex align-items-center gap-3">
              <div class="stat-icon bg-success bg-opacity-10 text-success"><i class="fas fa-users"></i></div>
              <div><div class="text-secondary small">Clientes totales</div><div class="fs-4 fw-bold" id="stat-customers">—</div></div>
            </div>
          </div>
        </div>
        <div class="col-sm-6 col-xl-3">
          <div class="card card-stat p-4">
            <div class="d-flex align-items-center gap-3">
              <div class="stat-icon bg-warning bg-opacity-10 text-warning"><i class="fas fa-shopping-bag"></i></div>
              <div><div class="text-secondary small">Pedidos totales</div><div class="fs-4 fw-bold" id="stat-orders">—</div></div>
            </div>
          </div>
        </div>
        <div class="col-sm-6 col-xl-3">
          <div class="card card-stat p-4">
            <div class="d-flex align-items-center gap-3">
              <div class="stat-icon bg-info bg-opacity-10 text-info"><i class="fas fa-sms"></i></div>
              <div><div class="text-secondary small">OTP 30 días</div><div class="fs-4 fw-bold" id="stat-otp">—</div></div>
            </div>
          </div>
        </div>
      </div>
      <div class="row g-3">
        <div class="col-md-6">
          <div class="card card-stat p-4">
            <h6 class="fw-semibold mb-3">Tenants por plan</h6>
            <div id="plan-breakdown">—</div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="card card-stat p-4">
            <h6 class="fw-semibold mb-3">Pedidos por estado</h6>
            <div id="orders-breakdown">—</div>
          </div>
        </div>
      </div>
    </section>

    <!-- Tenants -->
    <section id="section-tenants" style="display:none">
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h4 class="fw-bold mb-0">Tenants</h4>
        <div class="d-flex gap-2">
          <select class="form-select form-select-sm" id="plan-filter" onchange="loadTenants()">
            <option value="">Todos los planes</option>
            <option value="basic">Basic</option>
            <option value="pro">Pro</option>
            <option value="enterprise">Enterprise</option>
          </select>
          <button class="btn btn-sm btn-outline-primary" onclick="loadTenants()">
            <i class="fas fa-sync-alt"></i>
          </button>
        </div>
      </div>
      <div class="table-container bg-white">
        <table class="table table-hover mb-0">
          <thead class="table-light">
            <tr><th>Nombre</th><th>Subdominio</th><th>Plan</th><th>Estado</th><th>Creado</th><th>Acciones</th></tr>
          </thead>
          <tbody id="tenants-tbody"><tr><td colspan="6" class="text-center py-4 text-secondary">Cargando…</td></tr></tbody>
        </table>
      </div>
      <div id="tenants-pagination" class="mt-3 d-flex justify-content-between align-items-center text-secondary small"></div>
    </section>

    <!-- Auth Events -->
    <section id="section-auth-events" style="display:none">
      <div class="d-flex align-items-center justify-content-between mb-4">
        <h4 class="fw-bold mb-0">Auth Events</h4>
        <button class="btn btn-sm btn-outline-primary" onclick="loadAuthEvents()">
          <i class="fas fa-sync-alt me-1"></i>Actualizar
        </button>
      </div>
      <div class="table-container bg-white">
        <table class="table table-hover mb-0">
          <thead class="table-light">
            <tr><th>Fecha</th><th>Tenant</th><th>Phone/Email</th><th>Acción</th><th>Estado</th><th>IP</th></tr>
          </thead>
          <tbody id="events-tbody"><tr><td colspan="6" class="text-center py-4 text-secondary">Cargando…</td></tr></tbody>
        </table>
      </div>
    </section>

  </div>
</div>

<script>
const API = '';
let ADMIN_SECRET = localStorage.getItem('admin_secret') || '';
let _tenantsPage = 1;

function saveSecret() {
  ADMIN_SECRET = document.getElementById('secret-input').value.trim();
  if (!ADMIN_SECRET) return;
  localStorage.setItem('admin_secret', ADMIN_SECRET);
  document.getElementById('secret-modal').classList.remove('show');
  document.getElementById('main-layout').style.display = '';
  loadOverview();
}

function logout() {
  localStorage.removeItem('admin_secret');
  location.reload();
}

function headers() {
  return { 'X-Admin-Secret': ADMIN_SECRET, 'Content-Type': 'application/json' };
}

async function apiFetch(path) {
  const r = await fetch(API + path, { headers: headers() });
  if (r.status === 403) { logout(); return null; }
  if (!r.ok) throw new Error('HTTP ' + r.status);
  return r.json();
}

function showSection(name) {
  ['overview','tenants','auth-events'].forEach(s => {
    document.getElementById('section-' + s).style.display = s === name ? '' : 'none';
  });
  document.querySelectorAll('.nav-link').forEach(a => {
    a.classList.toggle('active', a.getAttribute('onclick').includes(name));
  });
  if (name === 'overview') loadOverview();
  if (name === 'tenants') loadTenants();
  if (name === 'auth-events') loadAuthEvents();
}

async function loadOverview() {
  try {
    const d = await apiFetch('/api/v1/admin/stats');
    if (!d) return;
    document.getElementById('stat-tenants').textContent = d.tenants_active;
    document.getElementById('stat-customers').textContent = d.customers_total.toLocaleString();
    document.getElementById('stat-orders').textContent = d.orders_total.toLocaleString();
    document.getElementById('stat-otp').textContent = d.otp_sends_30d.toLocaleString();

    const planEl = document.getElementById('plan-breakdown');
    planEl.innerHTML = Object.entries(d.tenants_by_plan || {}).map(([plan, cnt]) =>
      `<div class="d-flex justify-content-between py-1 border-bottom">
         <span class="text-capitalize">${plan}</span>
         <span class="badge bg-primary bg-opacity-10 text-primary">${cnt}</span>
       </div>`
    ).join('') || '<span class="text-secondary">Sin datos</span>';

    const ordEl = document.getElementById('orders-breakdown');
    ordEl.innerHTML = Object.entries(d.orders_by_status || {}).map(([st, cnt]) =>
      `<div class="d-flex justify-content-between py-1 border-bottom">
         <span class="text-capitalize">${st.replace(/_/g,' ')}</span>
         <span class="badge bg-secondary bg-opacity-10 text-secondary">${cnt}</span>
       </div>`
    ).join('') || '<span class="text-secondary">Sin datos</span>';

  } catch(e) { console.error(e); }
}

async function loadTenants(page) {
  _tenantsPage = page || 1;
  const plan = document.getElementById('plan-filter').value;
  const qs = `?page=${_tenantsPage}&page_size=20${plan ? '&plan=' + plan : ''}`;
  try {
    const d = await apiFetch('/api/v1/admin/tenants' + qs);
    if (!d) return;

    const tbody = document.getElementById('tenants-tbody');
    if (!d.items.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-secondary">No hay tenants</td></tr>';
      return;
    }

    tbody.innerHTML = d.items.map(t => `
      <tr>
        <td class="fw-medium">${esc(t.name)}</td>
        <td><code>${esc(t.subdomain)}</code></td>
        <td><span class="badge bg-${planColor(t.plan)}">${t.plan}</span></td>
        <td><span class="badge ${t.is_active ? 'bg-success' : 'bg-secondary'}">${t.is_active ? 'Activo' : 'Inactivo'}</span></td>
        <td class="text-secondary small">${new Date(t.created_at).toLocaleDateString('es')}</td>
        <td>
          <button class="btn btn-xs btn-outline-${t.is_active ? 'danger' : 'success'} btn-sm"
            onclick="toggleStatus('${t.id}', ${!t.is_active})">
            ${t.is_active ? 'Desactivar' : 'Activar'}
          </button>
        </td>
      </tr>`).join('');

    const pag = document.getElementById('tenants-pagination');
    pag.innerHTML = `
      <span>${d.total} tenants — Página ${d.page} de ${d.pages}</span>
      <div class="d-flex gap-1">
        ${d.page > 1 ? `<button class="btn btn-sm btn-outline-secondary" onclick="loadTenants(${d.page-1})">←</button>` : ''}
        ${d.page < d.pages ? `<button class="btn btn-sm btn-outline-secondary" onclick="loadTenants(${d.page+1})">→</button>` : ''}
      </div>`;
  } catch(e) { console.error(e); }
}

async function toggleStatus(id, active) {
  try {
    await fetch(`${API}/api/v1/admin/tenants/${id}/status`, {
      method: 'PATCH',
      headers: headers(),
      body: JSON.stringify({ is_active: active }),
    });
    loadTenants(_tenantsPage);
  } catch(e) { alert('Error: ' + e.message); }
}

async function loadAuthEvents() {
  try {
    const d = await apiFetch('/api/v1/admin/auth-events?limit=100');
    if (!d) return;
    const tbody = document.getElementById('events-tbody');
    if (!d.length) { tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-secondary">Sin eventos</td></tr>'; return; }
    tbody.innerHTML = d.map(e => `
      <tr>
        <td class="small text-secondary">${new Date(e.created_at).toLocaleString('es')}</td>
        <td><code class="small">${esc((e.tenant_id||'').slice(0,8)+'…')}</code></td>
        <td class="small">${esc(e.phone || e.email || '—')}</td>
        <td><span class="badge bg-light text-dark border">${esc(e.action)}</span></td>
        <td><span class="badge ${e.status==='success'?'bg-success':'bg-danger'}">${esc(e.status)}</span></td>
        <td class="small text-secondary">${esc(e.ip_address||'—')}</td>
      </tr>`).join('');
  } catch(e) { console.error(e); }
}

function planColor(p) { return {basic:'secondary',pro:'primary',enterprise:'warning text-dark'}[p] || 'light'; }
function esc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

// Init
if (ADMIN_SECRET) {
  document.getElementById('secret-modal').classList.remove('show');
  document.getElementById('main-layout').style.display = '';
  loadOverview();
}
</script>
</body>
</html>"""
