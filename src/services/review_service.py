"""
ReviewService — gestión de reseñas, NPS y encuestas de satisfacción.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

POSITIVE_WORDS = ["excelente", "perfecto", "bueno", "rapido", "encanto", "recomiendo",
                  "feliz", "genial", "increible", "satisfecho", "puntual", "calidad"]
NEGATIVE_WORDS = ["malo", "terrible", "pesimo", "demora", "roto", "sucio", "queja",
                  "insatisfecho", "decepcionante", "nunca", "horrible", "lento", "feo"]


class ReviewService:
    """Servicio de reseñas y calificaciones."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def submit_review(
        self,
        order_id: str,
        customer_id: str,
        rating: int,
        body: Optional[str] = None,
        delivery_rating: Optional[int] = None,
        nps_score: Optional[int] = None,
        product_id: Optional[str] = None,
        title: Optional[str] = None,
    ):
        """Envía una reseña. Auto-detecta sentimiento del cuerpo."""
        from models.review import Review

        if not 1 <= rating <= 5:
            raise ValueError("Rating debe estar entre 1 y 5.")
        if nps_score is not None and not 0 <= nps_score <= 10:
            raise ValueError("NPS score debe estar entre 0 y 10.")

        sentiment = self._detect_sentiment(body) if body else self._rating_to_sentiment(rating)

        review = Review(
            id=str(uuid.uuid4()),
            order_id=order_id,
            customer_id=customer_id,
            product_id=product_id,
            rating=rating,
            delivery_rating=delivery_rating,
            title=title,
            body=body,
            sentiment=sentiment,
            nps_score=nps_score,
            is_verified_purchase=True,
            is_published=True,
        )
        self.session.add(review)
        await self.session.commit()
        await self.session.refresh(review)
        logger.info(f"Reseña creada para orden {order_id}: rating={rating}, sentiment={sentiment}")
        return review

    async def get_order_reviews(self, order_id: str) -> list:
        """Reseñas de un pedido específico."""
        from models.review import Review
        result = await self.session.execute(
            select(Review).where(Review.order_id == order_id, Review.is_published == True)
        )
        return result.scalars().all()

    async def get_product_reviews(self, product_id: str, page: int = 1, limit: int = 20) -> tuple:
        """Reseñas de un producto con paginación."""
        from models.review import Review
        offset = (page - 1) * limit

        count_result = await self.session.execute(
            select(func.count(Review.id)).where(Review.product_id == product_id, Review.is_published == True)
        )
        total = count_result.scalar() or 0

        result = await self.session.execute(
            select(Review).where(Review.product_id == product_id, Review.is_published == True)
            .order_by(Review.created_at.desc()).offset(offset).limit(limit)
        )
        reviews = result.scalars().all()
        return reviews, total

    async def get_nps_score(self) -> dict:
        """Calcula NPS: promotores (9-10) - detractores (0-6) / total * 100."""
        from models.review import Review
        result = await self.session.execute(
            select(Review.nps_score).where(Review.nps_score.is_not(None))
        )
        scores = [row[0] for row in result.all() if row[0] is not None]

        if not scores:
            return {"nps": 0, "promoters": 0, "passives": 0, "detractors": 0, "total": 0}

        promoters = sum(1 for s in scores if s >= 9)
        passives = sum(1 for s in scores if 7 <= s <= 8)
        detractors = sum(1 for s in scores if s <= 6)
        total = len(scores)
        nps = round((promoters - detractors) / total * 100, 1)

        return {
            "nps": nps,
            "promoters": promoters,
            "passives": passives,
            "detractors": detractors,
            "total": total,
        }

    async def add_admin_response(self, review_id: str, response: str):
        """Agrega respuesta del admin a una reseña."""
        from models.review import Review
        result = await self.session.execute(select(Review).where(Review.id == review_id))
        review = result.scalar_one_or_none()
        if not review:
            raise ValueError(f"Reseña {review_id} no encontrada.")
        review.admin_response = response
        await self.session.commit()
        return review

    async def get_review_summary(self, product_id: Optional[str] = None) -> dict:
        """Resumen: rating promedio, distribución, total."""
        from models.review import Review

        query = select(
            func.avg(Review.rating).label("avg"),
            func.count(Review.id).label("total"),
        ).where(Review.is_published == True)

        if product_id:
            query = query.where(Review.product_id == product_id)

        result = await self.session.execute(query)
        row = result.one()

        # Distribución por rating
        dist_result = await self.session.execute(
            select(Review.rating, func.count(Review.id)).where(Review.is_published == True)
            .group_by(Review.rating)
        )
        distribution = {str(r): c for r, c in dist_result.all()}

        return {
            "avg_rating": round(float(row.avg or 0), 1),
            "total_reviews": row.total or 0,
            "rating_distribution": {str(i): distribution.get(str(i), 0) for i in range(1, 6)},
        }

    async def send_survey(self, order_id: str, customer, channel: str = "email") -> bool:
        """Envía encuesta post-compra y registra en BD."""
        from models.review import SatisfactionSurvey

        survey = SatisfactionSurvey(
            id=str(uuid.uuid4()),
            order_id=order_id,
            customer_id=getattr(customer, "id", str(uuid.uuid4())),
            sent_at=datetime.now(timezone.utc).isoformat(),
            channel=channel,
        )
        self.session.add(survey)
        await self.session.commit()

        # Enviar notificación
        try:
            from services.notification_service import NotificationService
            svc = NotificationService()
            order_mock = type("O", (), {"order_number": order_id})()
            await svc.send_post_purchase_survey(order_mock, customer)
        except Exception as e:
            logger.warning(f"Error enviando encuesta: {e}")

        return True

    def _detect_sentiment(self, text: str) -> str:
        """Detección de sentimiento por palabras clave."""
        if not text:
            return "neutral"
        text_lower = text.lower()
        pos_count = sum(1 for w in POSITIVE_WORDS if w in text_lower)
        neg_count = sum(1 for w in NEGATIVE_WORDS if w in text_lower)
        if pos_count > neg_count:
            return "positive"
        if neg_count > pos_count:
            return "negative"
        return "neutral"

    def _rating_to_sentiment(self, rating: int) -> str:
        if rating >= 4:
            return "positive"
        if rating <= 2:
            return "negative"
        return "neutral"
