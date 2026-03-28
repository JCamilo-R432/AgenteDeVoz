from typing import List, Dict, Optional, Any
"""Endpoints de FAQ avanzado."""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter(tags=["faq"])

_faq = None


def _get_faq():
    global _faq
    if _faq is None:
        from knowledge.faq_advanced import faq_manager
        _faq = faq_manager
    return _faq


class FAQEntryCreate(BaseModel):
    category: str
    question: str
    answer: str
    keywords: List[str]
    priority: int = 0


class FAQEntryUpdate(BaseModel):
    question: Optional[str] = None
    answer: Optional[str] = None
    keywords: Optional[List[str]] = None
    priority: Optional[int] = None


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/")
async def list_faq(category: Optional[str] = None):
    """Lista todas las entradas FAQ, agrupadas por categoría."""
    faq = _get_faq()
    entries = faq.get_all_entries()
    if category:
        entries = [e for e in entries if e.category == category]

    grouped: dict = {}
    for e in entries:
        grouped.setdefault(e.category, []).append(_entry_to_dict(e))

    return {"categories": list(grouped.keys()), "entries_by_category": grouped}


@router.get("/categories")
async def list_categories():
    """Lista categorías de FAQ disponibles."""
    faq = _get_faq()
    return {"categories": faq.get_categories()}


@router.get("/search")
async def search_faq(q: str, category: Optional[str] = None, limit: int = 5):
    """Busca en FAQ por palabras clave."""
    if not q or len(q) < 2:
        raise HTTPException(status_code=400, detail="La consulta debe tener al menos 2 caracteres.")
    faq = _get_faq()
    results = faq.search(q, category=category, limit=limit)
    return {
        "query": q,
        "results": [
            {
                **_entry_to_dict(r.entry),
                "score": round(r.score, 3),
                "matched_keywords": r.matched_keywords,
            }
            for r in results
        ],
    }


@router.get("/suggest")
async def suggest_faq(q: str, limit: int = 5):
    """Autocompletado de preguntas por prefijo."""
    faq = _get_faq()
    return {"prefix": q, "suggestions": faq.get_suggestions(q, limit=limit)}


@router.get("/voice-answer")
async def voice_answer(q: str):
    """Respuesta corta optimizada para voz."""
    faq = _get_faq()
    answer = faq.get_voice_answer(q)
    return {"query": q, "answer": answer}


@router.get("/{faq_id}")
async def get_faq_entry(faq_id: str):
    """Obtiene una entrada FAQ por ID."""
    faq = _get_faq()
    all_entries = faq.get_all_entries()
    entry = next((e for e in all_entries if e.id == faq_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"FAQ '{faq_id}' no encontrado.")
    entry.views += 1
    return _entry_to_dict(entry)


# ── Endpoints admin ───────────────────────────────────────────────────────────

@router.post("/", dependencies=[Depends(get_current_admin)], status_code=201)
async def add_faq_entry(req: FAQEntryCreate):
    """Agrega entrada personalizada de FAQ."""
    from knowledge.faq_advanced import FAQEntry
    faq = _get_faq()
    entry = FAQEntry(
        id=f"custom-{str(uuid.uuid4())[:8]}",
        category=req.category,
        question=req.question,
        answer=req.answer,
        keywords=req.keywords,
        priority=req.priority,
    )
    faq.add_custom_entry(entry)
    return _entry_to_dict(entry)


@router.put("/{faq_id}", dependencies=[Depends(get_current_admin)])
async def update_faq_entry(faq_id: str, req: FAQEntryUpdate):
    """Actualiza entrada personalizada."""
    faq = _get_faq()
    entry = faq.update_custom_entry(faq_id, req.model_dump(exclude_none=True))
    if not entry:
        raise HTTPException(status_code=404, detail=f"Entrada '{faq_id}' no encontrada o no es editable.")
    return _entry_to_dict(entry)


@router.delete("/{faq_id}", dependencies=[Depends(get_current_admin)])
async def delete_faq_entry(faq_id: str):
    """Elimina entrada personalizada."""
    faq = _get_faq()
    removed = faq.remove_custom_entry(faq_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Entrada '{faq_id}' no encontrada o no es eliminable.")
    return {"deleted": True, "id": faq_id}


def _entry_to_dict(entry) -> dict:
    return {
        "id": entry.id,
        "category": entry.category,
        "question": entry.question,
        "answer": entry.answer,
        "keywords": entry.keywords,
        "priority": entry.priority,
        "views": entry.views,
    }
