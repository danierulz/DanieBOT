from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from database.models import Customer, Order, OrderEvent, OrderItem, ProductVariant, Products
from services.advisor_notify import notify_advisor_new_web_order, notify_advisor_order_received
from services.order_code import generate_order_code
from services.pricing import unit_price_for_product


def _validate_line(db: Session, item: dict) -> dict:
    product = db.query(Products).filter(Products.product_id == item["id"]).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Producto {item['id']} no encontrado")
    if not bool(product.status):
        raise HTTPException(
            status_code=400,
            detail=f"El producto {item.get('titulo', item['id'])} no está disponible.",
        )

    variant_id = item.get("variant_id")
    if variant_id:
        variant = (
            db.query(ProductVariant)
            .filter(
                ProductVariant.variant_id == variant_id,
                ProductVariant.product_id == product.product_id,
            )
            .first()
        )
        if not variant or not variant.activo:
            raise HTTPException(
                status_code=400,
                detail=f"Variante no disponible para {item.get('titulo', product.item_title)}",
            )
        if not variant.encargo_habilitado and variant.qty_stock_local < item["cantidad"]:
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para {item.get('titulo', product.item_title)}",
            )
    else:
        stock_int = 0
        for v in product.variants or []:
            if v.activo:
                stock_int += int(v.qty_stock_local or 0)
        if stock_int < item["cantidad"] and not any(
            v.encargo_habilitado for v in (product.variants or []) if v.activo
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Stock insuficiente para {item.get('titulo', product.item_title)}",
            )

    server_unit = unit_price_for_product(product)
    client_unit = float(item["precio"])
    if abs(client_unit - server_unit) > 0.5:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Precio no válido para {item.get('titulo', product.item_title)}. "
                f"Recargá la página e intentá de nuevo (esperado ${server_unit:,.0f})."
            ).replace(",", "."),
        )
    unit_price = server_unit
    qty = int(item["cantidad"])
    subtotal = round(unit_price * qty, 2)
    title = item.get("titulo") or product.item_title or product.name or f"Producto {product.product_id}"

    return {
        "product_id": product.product_id,
        "variant_id": variant_id,
        "title_snapshot": title,
        "quantity": qty,
        "unit_price": unit_price,
        "subtotal": subtotal,
    }


def build_whatsapp_message(order_code: str, lines: list[dict], total: float, note: str | None = None) -> str:
    parts = [
        f"Pedido {order_code}",
        "(solicitud desde la web — no modificar este código)",
        "",
        "Detalle:",
    ]
    for i, line in enumerate(lines, 1):
        parts.append(
            f"{i}. {line['title_snapshot']} — ${line['subtotal']:,.0f} "
            f"(${line['unit_price']:,.0f} x {line['quantity']})"
        )
    parts.append("")
    parts.append(f"Total: ${total:,.0f}")
    if note:
        parts.append("")
        parts.append(f"Nota: {note}")
    return "\n".join(parts).replace(",", ".")


def create_order_from_cart(
    db: Session,
    items: list[dict],
    *,
    customer_name: str | None = None,
    customer_phone: str | None = None,
    note: str | None = None,
    cart_snapshot: list[dict] | None = None,
) -> tuple[Order, str]:
    if not items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    validated_lines = [_validate_line(db, it) for it in items]
    total = round(sum(line["subtotal"] for line in validated_lines), 2)

    order_code = generate_order_code()
    while db.query(Order).filter(Order.order_code == order_code).first():
        order_code = generate_order_code()

    new_order = Order(
        order_code=order_code,
        customer_name=customer_name,
        customer_phone=customer_phone,
        total=total,
        note=note,
        status="enviado_whatsapp",
        source="web",
        channel="wa_me",
        cart_snapshot=cart_snapshot or items,
    )
    db.add(new_order)
    db.flush()

    for line in validated_lines:
        db.add(
            OrderItem(
                order_id=new_order.order_id,
                product_id=line["product_id"],
                variant_id=line.get("variant_id"),
                title_snapshot=line["title_snapshot"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                subtotal=line["subtotal"],
            )
        )

    db.add(
        OrderEvent(
            order_id=new_order.order_id,
            event_type="created_web",
            payload={"order_code": order_code, "total": total},
        )
    )
    db.commit()
    db.refresh(new_order)

    mensaje = build_whatsapp_message(order_code, validated_lines, total, note)
    notify_advisor_new_web_order(new_order)
    return new_order, mensaje


def format_order_summary_for_bot(order: Order) -> str:
    lines = [f"*Pedido {order.order_code}*", f"Estado: {status_label(order.status)}", ""]
    for it in order.items:
        lines.append(
            f"• {it.title_snapshot} x{it.quantity} — ${it.subtotal:,.0f}".replace(",", ".")
        )
    lines.append("")
    lines.append(f"*Total:* ${order.total:,.0f}".replace(",", "."))
    return "\n".join(lines)


def status_label(status: str) -> str:
    labels = {
        "borrador": "Borrador",
        "enviado_whatsapp": "Enviado por WhatsApp (pendiente de lectura)",
        "recibido": "Recibido — en revisión",
        "en_revision": "En revisión",
        "confirmado": "Confirmado",
        "cancelado": "Cancelado",
        "pendiente": "Pendiente",
    }
    return labels.get(status, status)


def link_order_to_whatsapp(
    db: Session,
    order: Order,
    customer: Customer,
    wa_id: str,
) -> Order:
    order.whatsapp_wa_id = wa_id
    order.customer_id = customer.customer_id
    if order.status == "enviado_whatsapp":
        order.status = "recibido"
    db.add(
        OrderEvent(
            order_id=order.order_id,
            event_type="wa_message_received",
            payload={"wa_id": wa_id},
        )
    )
    db.commit()
    db.refresh(order)
    notify_advisor_order_received(
        order,
        customer_name=customer.display_name,
        customer_wa_id=wa_id,
    )
    return order


def get_order_by_code(db: Session, order_code: str) -> Order | None:
    return (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.order_code == order_code)
        .first()
    )


def update_order_status(db: Session, order: Order, new_status: str) -> Order:
    allowed = {"borrador", "enviado_whatsapp", "recibido", "en_revision", "confirmado", "cancelado", "pendiente"}
    if new_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Estado inválido: {new_status}")
    old = order.status
    order.status = new_status
    if new_status == "confirmado":
        from datetime import datetime

        order.confirmed_at = datetime.utcnow()
    db.add(
        OrderEvent(
            order_id=order.order_id,
            event_type="status_changed",
            payload={"from": old, "to": new_status},
        )
    )
    db.commit()
    db.refresh(order)
    return order
