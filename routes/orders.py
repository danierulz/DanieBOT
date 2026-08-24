from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from auth.auth import get_current_user
from config import get_whatsapp_bot_number
from database.init_db import get_db_fastApi
from database.models import Order, OrderEvent
import logging

from sqlalchemy import func

from services.app_log import log_event
from services.order_service import create_order_from_cart, status_label, update_order_status

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pedidos"])


class ItemIn(BaseModel):
    id: int
    titulo: str
    precio: float
    cantidad: int = Field(ge=1)
    variant_id: Optional[int] = None
    color_id: Optional[int] = None


class PedidoIn(BaseModel):
    items: List[ItemIn]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    note: Optional[str] = None
    cart_snapshot: Optional[list] = None


class PedidoStatusUpdate(BaseModel):
    status: str


@router.post("/api/whatsapp/pedido")
def crear_pedido(pedido: PedidoIn, db: Session = Depends(get_db_fastApi)):
    items = [it.model_dump() for it in pedido.items]
    snapshot = pedido.cart_snapshot if pedido.cart_snapshot is not None else items

    try:
        new_order, mensaje, reused = create_order_from_cart(
            db,
            items,
            customer_name=pedido.customer_name,
            customer_phone=pedido.customer_phone,
            note=pedido.note,
            cart_snapshot=snapshot,
        )
    except HTTPException as exc:
        titles = [it.titulo for it in pedido.items]
        log_event(
            logger,
            "order.create_rejected",
            detail=str(exc.detail),
            status_code=exc.status_code,
            titles=titles,
            product_ids=[it.id for it in pedido.items],
        )
        raise
    return {
        "status": "ok",
        "order_id": new_order.order_id,
        "order_code": new_order.order_code,
        "mensaje": mensaje,
        "whatsapp_number": get_whatsapp_bot_number(),
        "reused": reused,
    }


@router.get("/api/admin/pedidos")
def admin_listar_pedidos(
    db: Session = Depends(get_db_fastApi),
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    _user=Depends(get_current_user),
):
    q = db.query(Order).options(joinedload(Order.items), joinedload(Order.customer))
    if status:
        q = q.filter(Order.status == status)
    rows = q.order_by(Order.created_at.desc()).offset(offset).limit(min(limit, 200)).all()
    retry_map: dict[int, int] = {}
    if rows:
        counted = (
            db.query(OrderEvent.order_id, func.count(OrderEvent.event_id))
            .filter(
                OrderEvent.order_id.in_([o.order_id for o in rows]),
                OrderEvent.event_type == "web_retry",
            )
            .group_by(OrderEvent.order_id)
            .all()
        )
        retry_map = {oid: int(n) for oid, n in counted}
    return {
        "items": [
            {
                "order_id": o.order_id,
                "order_code": o.order_code,
                "status": o.status,
                "status_label": status_label(o.status),
                "total": o.total,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "customer_name": o.customer_name
                or (o.customer.display_name if o.customer else None),
                "whatsapp_wa_id": o.whatsapp_wa_id,
                "pending_whatsapp": o.status == "enviado_whatsapp" and not o.whatsapp_wa_id,
                "retry_count": retry_map.get(o.order_id, 0),
                "lines": [
                    {
                        "title": li.title_snapshot,
                        "quantity": li.quantity,
                        "unit_price": li.unit_price,
                        "subtotal": li.subtotal,
                        "size": li.size_label_snapshot,
                        "color": li.color_label_snapshot,
                    }
                    for li in o.items
                ],
            }
            for o in rows
        ]
    }


@router.patch("/api/admin/pedidos/{order_id}")
def admin_actualizar_pedido(
    order_id: int,
    body: PedidoStatusUpdate,
    db: Session = Depends(get_db_fastApi),
    _user=Depends(get_current_user),
):
    order = db.query(Order).filter(Order.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    order = update_order_status(db, order, body.status)
    return {
        "status": "ok",
        "order_id": order.order_id,
        "order_code": order.order_code,
        "new_status": order.status,
    }
