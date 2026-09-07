# -*- coding: utf-8 -*-
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.work_type import WorkType
from app.models.assignment import Assignment

router = APIRouter()


class WorkIn(BaseModel):
    Code: str
    Name: str
    Category: Optional[str] = ""
    Frequency: Optional[str] = "Ежегодно"
    DurationHours: Optional[float] = 1
    Price: Optional[float] = 0
    RequiredCert: Optional[str] = ""
    Description: Optional[str] = ""


def to_dict(w):
    return {
        "ID": w.id, "Code": w.code, "Name": w.name,
        "Category": w.category or "", "Frequency": w.frequency or "",
        "DurationHours": w.duration_hours or 0, "Price": w.price or 0,
        "RequiredCert": w.required_cert or "", "Description": w.description or "",
    }


@router.get("/")
def list_works(db: Session = Depends(get_db)):
    items = db.query(WorkType).order_by(WorkType.code).all()
    return {"ok": True, "data": [to_dict(w) for w in items]}


@router.post("/")
def create_work(data: WorkIn, db: Session = Depends(get_db)):
    w = WorkType(
        id=f"WRK-{uuid.uuid4().hex[:8]}",
        code=data.Code, name=data.Name, category=data.Category or "",
        frequency=data.Frequency or "Ежегодно",
        duration_hours=data.DurationHours or 0, price=data.Price or 0,
        required_cert=data.RequiredCert or "", description=data.Description or "",
    )
    db.add(w)
    db.commit()
    return {"ok": True, "data": to_dict(w)}



@router.get("/{wid}")
def get_work(wid: str, db: Session = Depends(get_db)):
    w = db.query(WorkType).filter(WorkType.id == wid).first()
    if not w:
        raise HTTPException(404, "Вид работы не найден")
    return {"ok": True, "data": to_dict(w)}


@router.put("/{wid}")
def update_work(wid: str, data: WorkIn, db: Session = Depends(get_db)):
    w = db.query(WorkType).filter(WorkType.id == wid).first()
    if not w:
        raise HTTPException(404, "Вид работы не найден")
    w.code = data.Code
    w.name = data.Name
    w.category = data.Category or ""
    w.frequency = data.Frequency or w.frequency
    w.duration_hours = data.DurationHours or 0
    w.price = data.Price or 0
    w.required_cert = data.RequiredCert or ""
    w.description = data.Description or ""
    db.commit()
    return {"ok": True, "data": to_dict(w)}


@router.delete("/{wid}")
def delete_work(wid: str, db: Session = Depends(get_db)):
    used = db.query(Assignment).filter(Assignment.work_type_id == wid).first()
    if used:
        raise HTTPException(400, "Этот вид работы используется в назначениях — сначала удалите их")
    w = db.query(WorkType).filter(WorkType.id == wid).first()
    if not w:
        raise HTTPException(404, "Вид работы не найден")
    db.delete(w)
    db.commit()
    return {"ok": True}
