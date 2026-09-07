# -*- coding: utf-8 -*-
import uuid
import json
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.company import Company
from app.config import CONFIG

router = APIRouter()
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"


class CompanySchema(BaseModel):
    name: str
    inn: str
    kpp: Optional[str] = ""
    ogrn: Optional[str] = ""
    address: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    bank: Optional[str] = ""
    bik: Optional[str] = ""
    account: Optional[str] = ""
    corr_account: Optional[str] = ""
    director: Optional[str] = ""
    accountant: Optional[str] = ""
    invoice_prefix: Optional[str] = "СЧ"
    vat_rate: Optional[float] = 0.0
    is_default: Optional[bool] = False


def company_dict(c: Company) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "inn": c.inn or "",
        "kpp": c.kpp or "",
        "ogrn": c.ogrn or "",
        "address": c.address or "",
        "phone": c.phone or "",
        "email": c.email or "",
        "bank": c.bank or "",
        "bik": c.bik or "",
        "account": c.account or "",
        "corr_account": c.corr_account or "",
        "director": c.director or "",
        "accountant": c.accountant or "",
        "invoice_prefix": c.invoice_prefix or "СЧ",
        "vat_rate": c.vat_rate or 0.0,
        "is_default": bool(c.is_default),
    }


def sync_default_to_config(c: Company):
    """Синхронизируем основную организацию в config.json для обратной совместимости"""
    try:
        if CONFIG_PATH.exists():
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        else:
            cfg = {}
        cfg["company"] = {
            "name": c.name,
            "inn": c.inn or "",
            "kpp": c.kpp or "",
            "ogrn": c.ogrn or "",
            "address": c.address or "",
            "phone": c.phone or "",
            "email": c.email or "",
            "bank": c.bank or "",
            "bik": c.bik or "",
            "account": c.account or "",
            "corrAccount": c.corr_account or "",
            "director": c.director or "",
            "accountant": c.accountant or "",
            "invoicePrefix": c.invoice_prefix or "СЧ",
            "vatRate": float(c.vat_rate or 0.0),
        }
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        if isinstance(CONFIG, dict):
            CONFIG["company"] = cfg["company"]
    except Exception:
        pass


@router.get("/")
def list_companies(db: Session = Depends(get_db)):
    rows = db.query(Company).order_by(Company.is_default.desc(), Company.created_at.asc()).all()
    # Если в таблице пусто, но есть в CONFIG - автоматически инициализируем
    if not rows and isinstance(CONFIG, dict) and CONFIG.get("company"):
        comp_cfg = CONFIG["company"]
        c = Company(
            id=f"COMP-{uuid.uuid4().hex[:8]}",
            name=comp_cfg.get("name") or "ООО «Организация»",
            inn=comp_cfg.get("inn") or "",
            kpp=comp_cfg.get("kpp") or "",
            ogrn=comp_cfg.get("ogrn") or "",
            address=comp_cfg.get("address") or "",
            phone=comp_cfg.get("phone") or "",
            email=comp_cfg.get("email") or "",
            bank=comp_cfg.get("bank") or "",
            bik=comp_cfg.get("bik") or "",
            account=comp_cfg.get("account") or "",
            corr_account=comp_cfg.get("corrAccount") or "",
            director=comp_cfg.get("director") or "",
            accountant=comp_cfg.get("accountant") or "",
            invoice_prefix=comp_cfg.get("invoicePrefix") or "СЧ",
            vat_rate=float(comp_cfg.get("vatRate") or 0.0),
            is_default=True,
        )
        db.add(c)
        db.commit()
        rows = [c]
    return {"ok": True, "data": [company_dict(r) for r in rows]}


@router.post("/")
def create_company(data: CompanySchema, db: Session = Depends(get_db)):
    if not data.name.strip() or not data.inn.strip():
        raise HTTPException(400, "Название организации и ИНН обязательны для заполнения")

    has_default = db.query(Company).filter(Company.is_default == True).first()
    is_def = bool(data.is_default) or (has_default is None)

    if is_def and has_default:
        db.query(Company).update({Company.is_default: False})

    c = Company(
        id=f"COMP-{uuid.uuid4().hex[:8]}",
        name=data.name.strip(),
        inn=data.inn.strip(),
        kpp=(data.kpp or "").strip(),
        ogrn=(data.ogrn or "").strip(),
        address=(data.address or "").strip(),
        phone=(data.phone or "").strip(),
        email=(data.email or "").strip(),
        bank=(data.bank or "").strip(),
        bik=(data.bik or "").strip(),
        account=(data.account or "").strip(),
        corr_account=(data.corr_account or "").strip(),
        director=(data.director or "").strip(),
        accountant=(data.accountant or "").strip(),
        invoice_prefix=(data.invoice_prefix or "СЧ").strip() or "СЧ",
        vat_rate=float(data.vat_rate or 0.0),
        is_default=is_def,
    )
    db.add(c)
    db.commit()
    db.refresh(c)

    if is_def:
        sync_default_to_config(c)

    return {"ok": True, "data": company_dict(c)}


@router.get("/{cid}")
def get_company_by_id(cid: str, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(404, "Организация не найдена")
    return {"ok": True, "data": company_dict(c)}


@router.put("/{cid}")
def update_company(cid: str, data: CompanySchema, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(404, "Организация не найдена")

    if not data.name.strip() or not data.inn.strip():
        raise HTTPException(400, "Название организации и ИНН обязательны для заполнения")

    if data.is_default and not c.is_default:
        db.query(Company).filter(Company.id != cid).update({Company.is_default: False})
        c.is_default = True
    elif data.is_default is False and c.is_default:
        # Не даем отключить статус по умолчанию, если это единственная компания
        total = db.query(Company).count()
        if total <= 1:
            c.is_default = True
        else:
            c.is_default = False

    c.name = data.name.strip()
    c.inn = data.inn.strip()
    c.kpp = (data.kpp or "").strip()
    c.ogrn = (data.ogrn or "").strip()
    c.address = (data.address or "").strip()
    c.phone = (data.phone or "").strip()
    c.email = (data.email or "").strip()
    c.bank = (data.bank or "").strip()
    c.bik = (data.bik or "").strip()
    c.account = (data.account or "").strip()
    c.corr_account = (data.corr_account or "").strip()
    c.director = (data.director or "").strip()
    c.accountant = (data.accountant or "").strip()
    c.invoice_prefix = (data.invoice_prefix or "СЧ").strip() or "СЧ"
    c.vat_rate = float(data.vat_rate or 0.0)

    db.commit()
    db.refresh(c)

    if c.is_default:
        sync_default_to_config(c)

    return {"ok": True, "data": company_dict(c)}


@router.post("/{cid}/set-default")
def set_default_company(cid: str, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(404, "Организация не найдена")

    db.query(Company).update({Company.is_default: False})
    c.is_default = True
    db.commit()
    db.refresh(c)

    sync_default_to_config(c)
    return {"ok": True, "data": company_dict(c)}


@router.delete("/{cid}")
def delete_company(cid: str, db: Session = Depends(get_db)):
    c = db.query(Company).filter(Company.id == cid).first()
    if not c:
        raise HTTPException(404, "Организация не найдена")

    total = db.query(Company).count()
    if total <= 1:
        raise HTTPException(400, "Нельзя удалить единственную организацию")

    was_default = c.is_default
    db.delete(c)
    db.commit()

    if was_default:
        next_c = db.query(Company).first()
        if next_c:
            next_c.is_default = True
            db.commit()
            sync_default_to_config(next_c)

    return {"ok": True}
