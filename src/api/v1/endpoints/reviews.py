"""Endpoints de Reseñas, NPS y Encuestas."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["reviews"])


class SubmitReviewRequest(BaseModel):
    order_id: str
    customer_id: str
    rating: int = Field(..., ge=1, le=5)
    body: Optional[str] = None
    title: Optional[str] = None
    delivery_rating: Optional[int] = Field(None, ge=1, le=5)
    nps_score: Optional[int] = Field(None, ge=0, le=10)
    product_id: Optional[str] = None


class AdminResponseRequest(BaseModel):
    response: str


def _get_service(db: AsyncSession):
    from services.review_service import ReviewService
    return ReviewService(db)


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.post("/submit", status_code=201)
async def submit_review(req: SubmitReviewRequest, db: AsyncSession = Depends(get_db)):
    """Envía una reseña de producto o servicio."""
    svc = _get_service(db)
    try:
        review = await svc.submit_review(
            order_id=req.order_id,
            customer_id=req.customer_id,
            rating=req.rating,
            body=req.body,
            delivery_rating=req.delivery_rating,
            nps_score=req.nps_score,
            product_id=req.product_id,
            title=req.title,
        )
        return {
            "id": review.id,
            "rating": review.rating,
            "sentiment": review.sentiment,
            "message": "Gracias por tu reseña. Tu opinión es muy importante para nosotros.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orders/{order_id}")
async def get_order_reviews(order_id: str, db: AsyncSession = Depends(get_db)):
    """Reseñas de un pedido específico."""
    svc = _get_service(db)
    reviews = await svc.get_order_reviews(order_id)
    return {
        "order_id": order_id,
        "reviews": [_review_to_dict(r) for r in reviews],
    }


@router.get("/products/{product_id}")
async def get_product_reviews(
    product_id: str, page: int = 1, limit: int = 20, db: AsyncSession = Depends(get_db)
):
    """Reseñas de un producto con paginación."""
    svc = _get_service(db)
    reviews, total = await svc.get_product_reviews(product_id, page, limit)
    summary = await svc.get_review_summary(product_id)
    return {
        "product_id": product_id,
        "total": total,
        "page": page,
        "summary": summary,
        "reviews": [_review_to_dict(r) for r in reviews],
    }


# ── Endpoints admin ───────────────────────────────────────────────────────────

@router.get("/nps/score", dependencies=[Depends(get_current_admin)])
async def get_nps_score(db: AsyncSession = Depends(get_db)):
    """NPS score actual."""
    svc = _get_service(db)
    return await svc.get_nps_score()


@router.get("/", dependencies=[Depends(get_current_admin)])
async def list_reviews(
    rating: Optional[int] = None,
    sentiment: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Lista todas las reseñas con filtros."""
    from sqlalchemy import select
    from models.review import Review

    query = select(Review).where(Review.is_published == True)
    if rating:
        query = query.where(Review.rating == rating)
    if sentiment:
        query = query.where(Review.sentiment == sentiment)

    offset = (page - 1) * limit
    result = await db.execute(query.order_by(Review.created_at.desc()).offset(offset).limit(limit))
    reviews = result.scalars().all()
    return {
        "total": len(reviews),
        "reviews": [_review_to_dict(r) for r in reviews],
    }


@router.post("/{review_id}/respond", dependencies=[Depends(get_current_admin)])
async def admin_response(review_id: str, req: AdminResponseRequest, db: AsyncSession = Depends(get_db)):
    """Agrega respuesta del admin a una reseña."""
    svc = _get_service(db)
    try:
        review = await svc.add_admin_response(review_id, req.response)
        return {"id": review.id, "admin_response": review.admin_response}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/surveys/send", dependencies=[Depends(get_current_admin)])
async def send_survey(order_id: str, customer_phone: str, channel: str = "whatsapp", db: AsyncSession = Depends(get_db)):
    """Envía encuesta de satisfacción post-compra."""
    customer_mock = type("C", (), {"id": "admin_send", "phone": customer_phone, "email": None})()
    svc = _get_service(db)
    sent = await svc.send_survey(order_id, customer_mock, channel)
    return {"sent": sent, "order_id": order_id, "channel": channel}


@router.get("/analytics/satisfaction", dependencies=[Depends(get_current_admin)])
async def satisfaction_analytics(db: AsyncSession = Depends(get_db)):
    """Analítica de satisfacción: CSAT + NPS."""
    svc = _get_service(db)
    nps = await svc.get_nps_score()
    summary = await svc.get_review_summary()
    return {**nps, **summary}


def _review_to_dict(review) -> dict:
    return {
        "id": review.id,
        "order_id": review.order_id,
        "rating": review.rating,
        "delivery_rating": review.delivery_rating,
        "title": review.title,
        "body": review.body,
        "sentiment": review.sentiment,
        "nps_score": review.nps_score,
        "admin_response": review.admin_response,
        "created_at": review.created_at,
    }
