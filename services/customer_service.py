from datetime import datetime

from sqlalchemy.orm import Session

from database.models import Customer


def get_or_create_customer_by_wa_id(
    db: Session,
    wa_id: str,
    *,
    display_name: str | None = None,
    phone: str | None = None,
) -> Customer:
    customer = db.query(Customer).filter(Customer.wa_id == wa_id).first()
    if customer:
        if display_name and not customer.display_name:
            customer.display_name = display_name
        if phone and not customer.phone:
            customer.phone = phone
        customer.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(customer)
        return customer

    customer = Customer(
        wa_id=wa_id,
        display_name=display_name,
        phone=phone or wa_id,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def save_customer_email(
    db: Session,
    customer: Customer,
    email: str,
    *,
    marketing_consent: bool = False,
) -> Customer:
    customer.email = email.strip().lower()
    customer.email_verified = False
    if marketing_consent:
        customer.marketing_email_consent = True
        customer.marketing_email_consent_at = datetime.utcnow()
    customer.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(customer)
    return customer
