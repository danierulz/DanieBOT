from fastapi import HTTPException
from sqlalchemy.orm import Session

from config import get_default_promo_banner_text
from database.models.SiteSetting import SiteSetting

PROMO_TEXT_KEY = "promo_banner_text"
PROMO_ACTIVO_KEY = "promo_banner_activo"
PROMO_TEXT_MAX_LEN = 200


def get_promo_banner(db: Session) -> dict:
    rows = {
        row.key: row.value
        for row in db.query(SiteSetting)
        .filter(SiteSetting.key.in_((PROMO_TEXT_KEY, PROMO_ACTIVO_KEY)))
        .all()
    }
    raw_text = rows.get(PROMO_TEXT_KEY)
    if raw_text is None:
        text = get_default_promo_banner_text()
    else:
        text = str(raw_text).strip()
    raw_activo = rows.get(PROMO_ACTIVO_KEY)
    if raw_activo is None:
        activo = True
    else:
        activo = str(raw_activo).strip().lower() in ("1", "true", "on", "yes")
    return {"text": text, "activo": activo}


def get_promo_banner_text(db: Session | None = None) -> str:
    if db is not None:
        return get_promo_banner(db)["text"]
    from database.init_db import SessionLocal

    session = SessionLocal()
    try:
        return get_promo_banner(session)["text"]
    except Exception:
        return get_default_promo_banner_text()
    finally:
        session.close()


def _upsert(db: Session, key: str, value: str) -> None:
    row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SiteSetting(key=key, value=value))


def set_promo_banner(db: Session, text: str, activo: bool) -> dict:
    cleaned = (text or "").strip()
    if len(cleaned) > PROMO_TEXT_MAX_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"El texto de la franja no puede superar {PROMO_TEXT_MAX_LEN} caracteres.",
        )
    _upsert(db, PROMO_TEXT_KEY, cleaned)
    _upsert(db, PROMO_ACTIVO_KEY, "1" if activo else "0")
    db.commit()
    return get_promo_banner(db)
