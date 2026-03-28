from __future__ import annotations
from typing import Dict, List, Any
"""
Invoice service — creates and manages local Invoice records.
Generates basic PDF invoices when reportlab is available.
"""


import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import Invoice, Subscription
from models.tenant import Tenant

logger = logging.getLogger(__name__)

INVOICE_DIR = os.getenv("INVOICE_DIR", "/var/data/agentevoz/invoices")


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self._db = session

    # ── Create ─────────────────────────────────────────────────────────────────

    async def create_from_stripe(
        self,
        *,
        subscription_id: str,
        tenant_id: str,
        stripe_data: Dict[str, Any],
    ) -> Invoice:
        """
        Persist a Stripe invoice payload as a local Invoice record.
        Called from the webhook handler on invoice.paid / invoice.created events.
        """
        invoice_number = await self._next_invoice_number(tenant_id)

        paid_at: datetime  = None
        if stripe_data.get("status") == "paid" and stripe_data.get("status_transitions", {}).get("paid_at"):
            paid_at = datetime.fromtimestamp(
                stripe_data["status_transitions"]["paid_at"], tz=timezone.utc
            )

        invoice = Invoice(
            id=str(uuid.uuid4()),
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            stripe_invoice_id=stripe_data.get("id"),
            stripe_payment_intent_id=stripe_data.get("payment_intent"),
            invoice_number=invoice_number,
            status=stripe_data.get("status", "draft"),
            amount_due=stripe_data.get("amount_due", 0),
            amount_paid=stripe_data.get("amount_paid", 0),
            currency=stripe_data.get("currency", "usd"),
            period_start=_ts_to_dt(stripe_data.get("lines", {}).get("data", [{}])[0].get("period", {}).get("start")),
            period_end=_ts_to_dt(stripe_data.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")),
            due_date=_ts_to_dt(stripe_data.get("due_date")),
            paid_at=paid_at,
            hosted_invoice_url=stripe_data.get("hosted_invoice_url"),
            invoice_pdf_url=stripe_data.get("invoice_pdf"),
            line_items=self._extract_line_items(stripe_data),
        )
        self._db.add(invoice)
        await self._db.flush()

        # Generate local PDF
        try:
            pdf_path = await self._generate_pdf(invoice, tenant_id)
            if pdf_path:
                invoice.local_pdf_path = pdf_path
                await self._db.flush()
        except Exception as exc:
            logger.warning(f"PDF generation failed for invoice {invoice_number}: {exc}")

        return invoice

    # ── List / Get ─────────────────────────────────────────────────────────────

    async def list_invoices(
        self,
        tenant_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Invoice]:
        result = await self._db.execute(
            select(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .order_by(Invoice.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_invoice(self, invoice_id: str, tenant_id: str) -> Invoice :
        result = await self._db.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    # ── PDF generation ─────────────────────────────────────────────────────────

    async def _generate_pdf(self, invoice: Invoice, tenant_id: str) -> str :
        """
        Generate a PDF invoice using reportlab (if installed).
        Returns local file path, or None if reportlab is not available.
        """
        try:
            from reportlab.lib.pagesizes import A4  # type: ignore
            from reportlab.pdfgen import canvas  # type: ignore
        except ImportError:
            logger.debug("reportlab not installed — PDF generation skipped")
            return None

        os.makedirs(INVOICE_DIR, exist_ok=True)
        filename = f"INV-{invoice.invoice_number.replace('/', '-')}.pdf"
        filepath = os.path.join(INVOICE_DIR, filename)

        # Fetch tenant name for the PDF
        tenant_result = await self._db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        tenant_name = tenant.name if tenant else tenant_id

        c = canvas.Canvas(filepath, pagesize=A4)
        width, height = A4

        # Header
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, height - 60, "AgenteDeVoz")
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 80, "Factura de Servicio")

        # Invoice details
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, height - 130, f"Factura #{invoice.invoice_number}")
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 150, f"Cliente: {tenant_name}")
        c.drawString(50, height - 165, f"Estado: {invoice.status.upper()}")
        c.drawString(50, height - 180, f"Fecha: {invoice.created_at.strftime('%Y-%m-%d')}")

        if invoice.period_start and invoice.period_end:
            c.drawString(
                50, height - 195,
                f"Período: {invoice.period_start.strftime('%Y-%m-%d')} → {invoice.period_end.strftime('%Y-%m-%d')}"
            )

        # Amount
        amount_display = invoice.amount_paid / 100
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 240, f"Total: ${amount_display:,.2f} {invoice.currency.upper()}")

        # Line items
        if invoice.line_items:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, height - 280, "Detalle:")
            c.setFont("Helvetica", 9)
            y = height - 295
            for item in invoice.line_items[:10]:
                desc = item.get("description", "Servicio")[:60]
                amt = item.get("amount", 0) / 100
                c.drawString(60, y, f"• {desc} — ${amt:,.2f} {invoice.currency.upper()}")
                y -= 15

        # Footer
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawString(50, 50, "AgenteDeVoz — Agente Conversacional con IA")
        c.drawString(50, 38, "Este documento es generado automáticamente.")

        c.save()
        logger.info(f"PDF invoice generated: {filepath}")
        return filepath

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _next_invoice_number(self, tenant_id: str) -> str:
        from sqlalchemy import func
        result = await self._db.execute(
            select(func.count()).where(Invoice.tenant_id == tenant_id)
        )
        count = (result.scalar_one_or_none() or 0) + 1
        month = datetime.now(timezone.utc).strftime("%Y%m")
        short_tid = tenant_id[:6].upper()
        return f"{short_tid}-{month}-{count:04d}"

    @staticmethod
    def _extract_line_items(stripe_data: dict) -> List[dict]:
        items = []
        lines = stripe_data.get("lines", {}).get("data", [])
        for line in lines:
            items.append({
                "description": line.get("description", ""),
                "amount": line.get("amount", 0),
                "currency": line.get("currency", "usd"),
                "quantity": line.get("quantity", 1),
            })
        return items


def _ts_to_dt(ts: Optional[int]) -> datetime :
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc)
    except Exception:
        return None
