"""Endpoints de Productos e Inventario."""
import logging
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.deps import get_current_admin, get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["products"])


class ProductCreateRequest(BaseModel):
    sku: str
    name: str
    description: Optional[str] = None
    base_price: Decimal
    currency: str = "COP"
    category_id: Optional[str] = None
    initial_stock: int = 0


class StockUpdateRequest(BaseModel):
    quantity_delta: int
    reason: str = "manual"


class ReserveStockRequest(BaseModel):
    quantity: int
    order_id: str


# ── Endpoints públicos ────────────────────────────────────────────────────────

@router.get("/")
async def list_products(
    category: Optional[str] = None,
    in_stock: bool = False,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Lista productos con filtros opcionales."""
    from models.product import Product, Category

    query = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.inventory),
    ).where(Product.is_active == True)

    if category:
        subq = select(Category.id).where(Category.slug == category).scalar_subquery()
        query = query.where(Product.category_id == subq)

    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%") | Product.sku.ilike(f"%{search}%")
        )

    count_result = await db.execute(select(Product.id).where(Product.is_active == True))
    total = len(count_result.all())

    offset = (page - 1) * limit
    result = await db.execute(query.offset(offset).limit(limit))
    products = result.scalars().all()

    if in_stock:
        products = [p for p in products if p.inventory and p.inventory.is_in_stock]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "products": [_product_to_dict(p) for p in products],
    }


@router.get("/search")
async def search_products(q: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Búsqueda de productos por nombre o SKU."""
    from models.product import Product

    result = await db.execute(
        select(Product).where(
            Product.is_active == True,
            Product.name.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"),
        ).options(selectinload(Product.inventory)).limit(limit)
    )
    products = result.scalars().all()
    return {"query": q, "results": [_product_to_dict(p) for p in products]}


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Lista categorías activas."""
    from models.product import Category

    result = await db.execute(select(Category).where(Category.is_active == True))
    cats = result.scalars().all()
    return [{"id": c.id, "name": c.name, "slug": c.slug, "description": c.description} for c in cats]


@router.get("/{sku}")
async def get_product(sku: str, db: AsyncSession = Depends(get_db)):
    """Detalle de producto por SKU."""
    from models.product import Product

    result = await db.execute(
        select(Product).where(Product.sku == sku.upper()).options(
            selectinload(Product.category),
            selectinload(Product.inventory),
            selectinload(Product.variants),
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto '{sku}' no encontrado.")
    return _product_to_dict(product, full=True)


@router.get("/{sku}/stock")
async def get_stock(sku: str, db: AsyncSession = Depends(get_db)):
    """Estado de stock de un producto."""
    from models.product import Product

    result = await db.execute(
        select(Product).where(Product.sku == sku.upper()).options(selectinload(Product.inventory))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto '{sku}' no encontrado.")

    inv = product.inventory
    qty = inv.quantity_actual if inv else 0
    in_stock = inv.is_in_stock if inv else False

    return {
        "sku": sku,
        "name": product.name,
        "in_stock": in_stock,
        "quantity": qty,
        "message": (
            f"Sí, tenemos {qty} unidades disponibles de {product.name}." if in_stock
            else f"{product.name} no está disponible en este momento."
        ),
    }


# ── Endpoints admin ───────────────────────────────────────────────────────────

@router.post("/", dependencies=[Depends(get_current_admin)], status_code=201)
async def create_product(req: ProductCreateRequest, db: AsyncSession = Depends(get_db)):
    """Crea un nuevo producto."""
    from models.product import Product, Inventory

    product = Product(
        id=str(uuid.uuid4()),
        sku=req.sku.upper(),
        name=req.name,
        description=req.description,
        base_price=req.base_price,
        currency=req.currency,
        category_id=req.category_id,
    )
    db.add(product)
    await db.flush()

    inventory = Inventory(
        id=str(uuid.uuid4()),
        product_id=product.id,
        quantity_available=req.initial_stock,
    )
    db.add(inventory)
    await db.commit()
    await db.refresh(product)
    return _product_to_dict(product)


@router.put("/{sku}/stock", dependencies=[Depends(get_current_admin)])
async def update_stock(sku: str, req: StockUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Actualiza stock de un producto."""
    from models.product import Product, Inventory

    result = await db.execute(
        select(Product).where(Product.sku == sku.upper()).options(selectinload(Product.inventory))
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto '{sku}' no encontrado.")

    if not product.inventory:
        inv = Inventory(id=str(uuid.uuid4()), product_id=product.id, quantity_available=0)
        db.add(inv)
        await db.flush()
        product.inventory = inv

    product.inventory.quantity_available = max(
        0, product.inventory.quantity_available + req.quantity_delta
    )
    await db.commit()
    return {"sku": sku, "new_quantity": product.inventory.quantity_available, "reason": req.reason}


@router.post("/{sku}/reserve", dependencies=[Depends(get_current_admin)])
async def reserve_stock(sku: str, req: ReserveStockRequest, db: AsyncSession = Depends(get_db)):
    """Reserva stock para una orden."""
    from models.product import Product

    result = await db.execute(
        select(Product).where(Product.sku == sku.upper()).options(selectinload(Product.inventory))
    )
    product = result.scalar_one_or_none()
    if not product or not product.inventory:
        raise HTTPException(status_code=404, detail=f"Producto '{sku}' no encontrado.")

    available = product.inventory.quantity_actual
    if available < req.quantity:
        return {
            "success": False,
            "available": available,
            "requested": req.quantity,
            "message": f"Stock insuficiente. Solo hay {available} unidades disponibles.",
        }

    product.inventory.quantity_reserved += req.quantity
    await db.commit()
    return {
        "success": True,
        "reserved": req.quantity,
        "available_after": product.inventory.quantity_actual,
        "message": f"Reservadas {req.quantity} unidades de {product.name}.",
    }


@router.get("/stock/low", dependencies=[Depends(get_current_admin)])
async def get_low_stock(db: AsyncSession = Depends(get_db)):
    """Productos con stock bajo."""
    from models.product import Product, Inventory

    result = await db.execute(
        select(Product).join(Inventory, Inventory.product_id == Product.id).options(
            selectinload(Product.inventory)
        ).where(Product.is_active == True)
    )
    products = result.scalars().all()
    low_stock = [p for p in products if p.inventory and p.inventory.is_low_stock]
    return {
        "total_low_stock": len(low_stock),
        "products": [
            {
                "sku": p.sku,
                "name": p.name,
                "quantity": p.inventory.quantity_actual if p.inventory else 0,
                "minimum": p.inventory.quantity_minimum if p.inventory else 5,
            }
            for p in low_stock
        ],
    }


@router.get("/stock/report", dependencies=[Depends(get_current_admin)])
async def stock_report(db: AsyncSession = Depends(get_db)):
    """Reporte completo de inventario."""
    from models.product import Product, Inventory
    from sqlalchemy import func

    counts = await db.execute(
        select(
            func.count(Product.id).label("total_skus"),
            func.sum(Inventory.quantity_available).label("total_units"),
        ).join(Inventory, Inventory.product_id == Product.id).where(Product.is_active == True)
    )
    row = counts.one()
    return {
        "total_skus": row.total_skus or 0,
        "total_units": int(row.total_units or 0),
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }


def _product_to_dict(product, full: bool = False) -> dict:
    inv = product.inventory
    result = {
        "id": product.id,
        "sku": product.sku,
        "name": product.name,
        "base_price": float(product.base_price),
        "currency": product.currency,
        "is_active": product.is_active,
        "category": (
            {"id": product.category.id, "name": product.category.name}
            if getattr(product, "category", None) else None
        ),
        "inventory": {
            "quantity": inv.quantity_actual if inv else 0,
            "in_stock": inv.is_in_stock if inv else False,
            "is_low_stock": inv.is_low_stock if inv else True,
        } if inv else None,
    }
    if full:
        result["description"] = product.description
    return result
