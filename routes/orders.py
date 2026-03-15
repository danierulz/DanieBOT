from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from db import get_db
from models.orders import Order, OrderItem
from models.products import Products  # tu modelo de productos
import math

router = APIRouter()

class ItemIn(BaseModel):
    id: int
    titulo: str
    precio: float
    cantidad: int

class PedidoIn(BaseModel):
    items: List[ItemIn]
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    note: Optional[str] = None

@router.post("/api/whatsapp/pedido")
def crear_pedido(pedido: PedidoIn, db: Session = Depends(get_db)):
    if not pedido.items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    # Validar stock y calcular total
    total = 0.0
    order_items = []
    for it in pedido.items:
        product = db.query(Products).filter(Products.product_id == it.id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {it.id} no encontrado")
        # Si querés validar stock:
        try:
            stock_int = int(getattr(product, "stock", 0) or 0)
        except Exception:
            stock_int = 0
        if stock_int < it.cantidad:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {it.titulo}")
        unit_price = float(it.precio)
        subtotal = round(unit_price * it.cantidad, 2)
        total += subtotal
        order_items.append({
            "product_id": it.id,
            "title": it.titulo,
            "quantity": it.cantidad,
            "unit_price": unit_price,
            "subtotal": subtotal
        })

    # Crear Order y OrderItems en una transacción
    new_order = Order(
        customer_name=pedido.customer_name,
        customer_phone=pedido.customer_phone,
        total=round(total, 2),
        note=pedido.note,
        status="pendiente"
    )
    db.add(new_order)
    db.flush()  # para obtener new_order.order_id

    for oi in order_items:
        db_item = OrderItem(
            order_id=new_order.order_id,
            product_id=oi["product_id"],
            title=oi["title"],
            quantity=oi["quantity"],
            unit_price=oi["unit_price"],
            subtotal=oi["subtotal"]
        )
        db.add(db_item)

        # Opcional: decrementar stock
        product = db.query(Products).filter(Products.product_id == oi["product_id"]).first()
        if product and hasattr(product, "stock"):
            try:
                product.stock = max(0, int(product.stock) - oi["quantity"])
            except Exception:
                pass

    db.commit()
    db.refresh(new_order)

    # Armar mensaje para WhatsApp
    mensaje = "🛒 *Nuevo pedido* \n"
    mensaje += f"Pedido ID: {new_order.order_id}\n"
    if new_order.customer_name:
        mensaje += f"Cliente: {new_order.customer_name}\n"
    if new_order.customer_phone:
        mensaje += f"Tel: {new_order.customer_phone}\n"
    mensaje += "\nDetalle:\n"
    for it in order_items:
        mensaje += f"- {it['title']} x{it['quantity']} (${it['subtotal']})\n"
    mensaje += f"\n*Total:* ${round(total,2)}"

    # Enviar al bot de WhatsApp (placeholder)
    # Aquí llamás a tu función real que envía mensajes
    # send_whatsapp_message(to=BUSINESS_NUMBER, text=mensaje)
    print("DEBUG: Mensaje a enviar:", mensaje)

    return {"status": "ok", "order_id": new_order.order_id, "mensaje": mensaje}
################################################################################################
# 
###############################################################################################
@router.post("/api/whatsapp/pedido")
def crear_pedido(pedido: PedidoIn, db: Session = Depends(get_db)):
    if not pedido.items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    total = 0.0
    order_items = []
    for it in pedido.items:
        product = db.query(Products).filter(Products.product_id == it.id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Producto {it.id} no encontrado")
        stock_int = int(getattr(product, "stock", 0) or 0)
        if stock_int < it.cantidad:
            raise HTTPException(status_code=400, detail=f"Stock insuficiente para {it.titulo}")
        unit_price = float(it.precio)
        subtotal = round(unit_price * it.cantidad, 2)
        total += subtotal
        order_items.append({
            "product_id": it.id,
            "title": it.titulo,
            "quantity": it.cantidad,
            "unit_price": unit_price,
            "subtotal": subtotal
        })

    new_order = Order(
        customer_name=pedido.customer_name,
        customer_phone=pedido.customer_phone,
        total=round(total, 2),
        note=pedido.note,
        status="pendiente"
    )
    db.add(new_order)
    db.flush()

    for oi in order_items:
        db_item = OrderItem(
            order_id=new_order.order_id,
            product_id=oi["product_id"],
            title=oi["title"],
            quantity=oi["quantity"],
            unit_price=oi["unit_price"],
            subtotal=oi["subtotal"]
        )
        db.add(db_item)
        product = db.query(Products).filter(Products.product_id == oi["product_id"]).first()
        if product and hasattr(product, "stock"):
            try:
                product.stock = max(0, int(product.stock) - oi["quantity"])
            except Exception:
                pass

    db.commit()
    db.refresh(new_order)

    # Armar mensaje legible para WhatsApp
    lines = []
    lines.append("🛒 *Nuevo pedido*")
    lines.append(f"Pedido ID: {new_order.order_id}")
    if new_order.customer_name:
        lines.append(f"Cliente: {new_order.customer_name}")
    if new_order.customer_phone:
        lines.append(f"Tel: {new_order.customer_phone}")
    lines.append("")
    lines.append("Detalle:")
    for it in order_items:
        lines.append(f"- {it['title']} x{it['quantity']} (${it['subtotal']})")
    lines.append("")
    lines.append(f"*Total:* ${round(total,2)}")
    if new_order.note:
        lines.append("")
        lines.append(f"Nota: {new_order.note}")

    mensaje = "\n".join(lines)

    # Devolver mensaje y número para que el frontend abra WhatsApp
    return {
        "status": "ok",
        "order_id": new_order.order_id,
        "mensaje": mensaje,
        "whatsapp_number": BUSINESS_WHATSAPP_NUMBER
    }