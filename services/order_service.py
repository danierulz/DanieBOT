import logging
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from database.models import Customer, Order, OrderEvent, OrderItem, ProductVariant, Products
from services.advisor_notify import notify_advisor_new_web_order, notify_advisor_order_received
from services.app_log import log_event
from services.colors import product_requires_color, validate_line_color
from services.order_code import generate_order_code
from services.pricing import unit_price_for_product

logger = logging.getLogger(__name__)

RETRY_WINDOW_MINUTES = 45


def cart_fingerprint(lines: list[dict]) -> str:
    parts = []
    for line in lines:
        parts.append(
            f"{line.get('product_id')}:{line.get('variant_id') or ''}:{int(line.get('quantity') or 0)}"
        )
    return "|".join(sorted(parts))


def _fingerprint_from_order(order: Order) -> str:
    return cart_fingerprint(
        [
            {
                "product_id": it.product_id,
                "variant_id": it.variant_id,
                "quantity": it.quantity,
            }
            for it in (order.items or [])
        ]
    )


def _find_recent_pending_duplicate(
    db: Session, fingerprint: str, *, exclude_order_id: int | None = None
) -> Order | None:
    cutoff = datetime.utcnow() - timedelta(minutes=RETRY_WINDOW_MINUTES)
    q = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(
            Order.status == "enviado_whatsapp",
            Order.source == "web",
            Order.created_at >= cutoff,
        )
        .order_by(Order.created_at.desc())
        .limit(30)
    )
    for order in q.all():
        if exclude_order_id and order.order_id == exclude_order_id:
            continue
        if _fingerprint_from_order(order) == fingerprint:
            return order
    return None


def _line_option_parts(line: dict) -> str:
    parts = []
    if line.get("size_label_snapshot"):
        parts.append(f"Talle {line['size_label_snapshot']}")
    if line.get("color_label_snapshot"):
        parts.append(f"Color {line['color_label_snapshot']}")
    return " — ".join(parts)


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
    size_label_snapshot = None
    if variant_id:
        variant = (
            db.query(ProductVariant)
            .options(joinedload(ProductVariant.size), joinedload(ProductVariant.color))
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
        if variant.size:
            size_label_snapshot = variant.size.label
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

    color_row = validate_line_color(db, product.product_id, item.get("color_id"))
    color_id = color_row.color_id if color_row else None
    color_label_snapshot = color_row.label if color_row else None

    if variant_id and color_id is not None:
        variant_for_color = (
            db.query(ProductVariant)
            .filter(
                ProductVariant.variant_id == variant_id,
                ProductVariant.product_id == product.product_id,
            )
            .first()
        )
        if variant_for_color and variant_for_color.color_id is not None:
            if variant_for_color.color_id != color_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"El color seleccionado no coincide con el talle para {title}.",
                )

    if product_requires_color(db, product.product_id) and not variant_id:
        raise HTTPException(
            status_code=400,
            detail=f"Seleccioná un talle para {title}.",
        )

    return {
        "product_id": product.product_id,
        "variant_id": variant_id,
        "color_id": color_id,
        "size_label_snapshot": size_label_snapshot,
        "color_label_snapshot": color_label_snapshot,
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
        opts = _line_option_parts(line)
        head = f"{i}. {line['title_snapshot']}"
        if opts:
            head += f" — {opts}"
        parts.append(
            f"{head} — ${line['subtotal']:,.0f} "
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
) -> tuple[Order, str, bool]:
    if not items:
        raise HTTPException(status_code=400, detail="El carrito está vacío")

    validated_lines = [_validate_line(db, it) for it in items]
    total = round(sum(line["subtotal"] for line in validated_lines), 2)
    fingerprint = cart_fingerprint(validated_lines)

    existing = _find_recent_pending_duplicate(db, fingerprint)
    if existing:
        log_event(
            logger,
            "order.retry_same_cart",
            order_code=existing.order_code,
            order_id=existing.order_id,
            total=existing.total,
            items=[line["title_snapshot"] for line in validated_lines],
        )
        db.add(
            OrderEvent(
                order_id=existing.order_id,
                event_type="web_retry",
                payload={"order_code": existing.order_code, "fingerprint": fingerprint},
            )
        )
        db.commit()
        db.refresh(existing)
        mensaje = build_whatsapp_message(existing.order_code, validated_lines, existing.total, note)
        return existing, mensaje, True

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
                color_id=line.get("color_id"),
                size_label_snapshot=line.get("size_label_snapshot"),
                color_label_snapshot=line.get("color_label_snapshot"),
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
            payload={"order_code": order_code, "total": total, "fingerprint": fingerprint},
        )
    )
    db.commit()
    db.refresh(new_order)

    log_event(
        logger,
        "order.created_web",
        order_code=order_code,
        order_id=new_order.order_id,
        total=total,
        items=[
            {
                "title": line["title_snapshot"],
                "product_id": line["product_id"],
                "quantity": line["quantity"],
            }
            for line in validated_lines
        ],
    )
    mensaje = build_whatsapp_message(order_code, validated_lines, total, note)
    notify_advisor_new_web_order(new_order)
    return new_order, mensaje, False


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
    log_event(
        logger,
        "order.wa_linked",
        order_code=order.order_code,
        order_id=order.order_id,
        wa_id=wa_id,
        customer_name=customer.display_name,
        status=order.status,
    )
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
