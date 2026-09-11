# -*- coding: utf-8 -*-
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.assignment import Assignment
from app.models.execution import Execution

router = APIRouter()


class ObjectIn(BaseModel):
    Name: str
    Address: Optional[str] = ""
    Inn: Optional[str] = ""
    ContactPerson: Optional[str] = ""
    Phone: Optional[str] = ""
    Email: Optional[str] = ""
    Category: Optional[str] = ""
    FunctionalHazard: Optional[str] = "Ф3.1"
    FireHazardCategory: Optional[str] = "В"
    ConstructionHazard: Optional[str] = "С0"
    TotalArea: Optional[float] = 0.0
    Floors: Optional[int] = 1
    RiskLevel: Optional[str] = ""
    Notes: Optional[str] = ""


class DeleteIn(BaseModel):
    Reason: str


FIELDS = {
    "Name": "name", "Address": "address", "Inn": "inn",
    "ContactPerson": "contact_person", "Phone": "phone", "Email": "email",
    "Category": "category",
    "FunctionalHazard": "functional_hazard",
    "FireHazardCategory": "fire_hazard_category",
    "ConstructionHazard": "construction_hazard",
    "TotalArea": "total_area",
    "Floors": "floors",
    "RiskLevel": "risk_level",
    "Notes": "notes",
}


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"



def to_dict(o, db):
    assigns = db.query(Assignment).filter(
        Assignment.object_id == o.id,
        Assignment.status != "Удалено",
    ).all()
    execs = db.query(Execution).filter(Execution.object_id == o.id).all()
    today = date.today()
    return {
        "ID": o.id, "Name": o.name, "Address": o.address or "",
        "Inn": o.inn or "", "ContactPerson": o.contact_person or "",
        "Phone": o.phone or "", "Email": o.email or "",
        "Category": o.category or "",
        "FunctionalHazard": getattr(o, "functional_hazard", "Ф3.1") or "Ф3.1",
        "FireHazardCategory": getattr(o, "fire_hazard_category", "В") or "В",
        "ConstructionHazard": getattr(o, "construction_hazard", "С0") or "С0",
        "TotalArea": float(getattr(o, "total_area", 0.0) or 0.0),
        "Floors": int(getattr(o, "floors", 1) or 1),
        "RiskLevel": o.risk_level or "",
        "Notes": o.notes or "", "Status": o.status,
        "AssignmentsCount": len(assigns),
        "ExecutionsTotal": len(execs),
        "ExecutionsDone": sum(1 for e in execs if e.status == "Выполнено"),
        "Overdue": sum(1 for e in execs if e.status == "Запланировано" and e.planned_date < today),
        "TotalPrice": sum(a.total_price or 0 for a in assigns),
    }


@router.get("/")
def list_objects(db: Session = Depends(get_db)):
    items = db.query(Object).filter(Object.status != "Удалён").order_by(Object.name).all()
    return {"ok": True, "data": [to_dict(o, db) for o in items]}


@router.post("/")
def create_object(data: ObjectIn, db: Session = Depends(get_db)):
    o = Object(id=new_id("OBJ"), status="Активен")
    for key, field in FIELDS.items():
        val = getattr(data, key)
        if field == "total_area":
            setattr(o, field, float(val or 0.0))
        elif field == "floors":
            setattr(o, field, int(val or 1))
        else:
            setattr(o, field, val or "")
    db.add(o)
    db.commit()
    return {"ok": True, "data": to_dict(o, db)}


@router.get("/{oid}")
def get_object(oid: str, db: Session = Depends(get_db)):
    o = db.query(Object).filter(Object.id == oid).first()
    if not o:
        raise HTTPException(404, "Объект не найден")
    return {"ok": True, "data": to_dict(o, db)}


@router.put("/{oid}")
def update_object(oid: str, data: ObjectIn, db: Session = Depends(get_db)):
    o = db.query(Object).filter(Object.id == oid).first()
    if not o:
        raise HTTPException(404, "Объект не найден")
    for key, field in FIELDS.items():
        val = getattr(data, key)
        if field == "total_area":
            setattr(o, field, float(val or 0.0))
        elif field == "floors":
            setattr(o, field, int(val or 1))
        else:
            setattr(o, field, val or "")
    db.commit()
    return {"ok": True, "data": to_dict(o, db)}


@router.delete("/{oid}")
def delete_object(oid: str, data: DeleteIn, purge: bool = False, db: Session = Depends(get_db)):
    reason = (data.Reason or "").strip()
    if not reason:
        raise HTTPException(400, "Укажите причину удаления")
    o = db.query(Object).filter(Object.id == oid).first()
    if not o:
        raise HTTPException(404, "Объект не найден")

    # Если запрошено полное удаление (например, для тестовых объектов)
    if purge or "тест" in (o.name or "").lower() or oid.startswith("TEST-"):
        db.query(Execution).filter(Execution.object_id == oid).delete()
        db.query(Assignment).filter(Assignment.object_id == oid).delete()
        db.delete(o)
        db.commit()
        return {"ok": True, "archived_assignments": 0, "purged": True}

    o.status = "Удалён"
    o.delete_reason = reason
    now = datetime.now()
    full_reason = "Объект удалён: " + reason
    archived = 0
    for a in db.query(Assignment).filter(Assignment.object_id == oid, Assignment.status == "Активно").all():
        a.status = "Удалено"
        a.reason = full_reason
        a.deleted_at = now
        archived += 1
    db.commit()
    return {"ok": True, "archived_assignments": archived}
