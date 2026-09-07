# -*- coding: utf-8 -*-
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.execution import Execution
from app.services.periodicity import generate_schedule

router = APIRouter()


class AssignmentIn(BaseModel):
    ObjectId: str
    WorkId: str
    Frequency: Optional[str] = ""
    StartDate: str
    EndDate: str
    PricePerUnit: Optional[float] = 0
    Responsible: Optional[str] = ""
    Notes: Optional[str] = ""


class DeleteIn(BaseModel):
    Reason: str


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"



def to_dict(a, db):
    obj = db.query(Object).filter(Object.id == a.object_id).first()
    work = db.query(WorkType).filter(WorkType.id == a.work_type_id).first()
    execs = db.query(Execution).filter(Execution.assignment_id == a.id).all()
    return {
        "ID": a.id,
        "ObjectId": a.object_id,
        "ObjectName": obj.name if obj else "",
        "WorkId": a.work_type_id,
        "WorkName": work.name if work else "",
        "WorkCode": work.code if work else "",
        "Frequency": a.frequency,
        "StartDate": a.start_date.isoformat() if a.start_date else None,
        "EndDate": a.end_date.isoformat() if a.end_date else None,
        "PricePerUnit": a.price_per_unit or 0,
        "TotalPrice": a.total_price or 0,
        "PaidAmount": getattr(a, "paid_amount", 0) or 0,
        "Debt": max(0, (a.total_price or 0) - (getattr(a, "paid_amount", 0) or 0)),
        "Responsible": a.responsible or "",
        "Status": a.status,
        "Reason": a.reason or "",
        "DeletedAt": a.deleted_at.isoformat() if a.deleted_at else None,
        "Notes": a.notes or "",
        "ExecutionsTotal": len(execs),
        "ExecutionsDone": sum(1 for e in execs if e.status == "Выполнено"),
    }


@router.get("/")
def list_assignments(object_id: Optional[str] = None, include_deleted: bool = False, db: Session = Depends(get_db)):
    q = db.query(Assignment)
    if object_id:
        q = q.filter(Assignment.object_id == object_id)
    if not include_deleted:
        q = q.filter(Assignment.status != "Удалено")
    items = q.order_by(Assignment.start_date.desc()).all()
    return {"ok": True, "data": [to_dict(a, db) for a in items]}


@router.post("/")
def create_assignment(data: AssignmentIn, db: Session = Depends(get_db)):
    obj = db.query(Object).filter(Object.id == data.ObjectId).first()
    if not obj:
        raise HTTPException(404, "Объект не найден")
    work = db.query(WorkType).filter(WorkType.id == data.WorkId).first()
    if not work:
        raise HTTPException(404, "Вид работы не найден")
    try:
        start = date.fromisoformat(data.StartDate)
        end = date.fromisoformat(data.EndDate)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")
    if end < start:
        raise HTTPException(400, "Дата окончания раньше даты начала")
    freq = (data.Frequency or "").strip() or (work.frequency or "Разовая")
    price = data.PricePerUnit if data.PricePerUnit and data.PricePerUnit > 0 else (work.price or 0)
    schedule = generate_schedule(start, end, freq)
    if not schedule:
        raise HTTPException(400, "Не удалось построить расписание")
    a = Assignment(
        id=new_id("ASN"),
        object_id=obj.id,
        work_type_id=work.id,
        frequency=freq,
        start_date=start,
        end_date=end,
        price_per_unit=price,
        total_price=round(price * len(schedule), 2),
        responsible=data.Responsible or "",
        status="Активно",
        notes=data.Notes or "",
    )
    db.add(a)
    db.flush()
    for d in schedule:
        db.add(Execution(
            id=new_id("EX"),
            assignment_id=a.id,
            object_id=obj.id,
            work_type_id=work.id,
            planned_date=d,
            status="Запланировано",
        ))
    db.commit()
    return {"ok": True, "data": to_dict(a, db), "created": len(schedule)}


@router.delete("/{aid}")
def delete_assignment(aid: str, data: DeleteIn, db: Session = Depends(get_db)):
    """Удаление в архив: выполнение остаётся в календаре с пометкой."""
    reason = (data.Reason or "").strip()
    if not reason:
        raise HTTPException(400, "Укажите причину удаления")
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(404, "Назначение не найдено")
    a.status = "Удалено"
    a.reason = reason
    a.deleted_at = datetime.now()
    db.commit()
    return {"ok": True}


@router.post("/{aid}/restore")
def restore_assignment(aid: str, db: Session = Depends(get_db)):
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(404, "Назначение не найдено")
    a.status = "Активно"
    a.reason = None
    a.deleted_at = None
    db.commit()
    return {"ok": True, "data": to_dict(a, db)}


@router.post("/{aid}/regenerate")
def regenerate(aid: str, db: Session = Depends(get_db)):
    a = db.query(Assignment).filter(Assignment.id == aid).first()
    if not a:
        raise HTTPException(404, "Назначение не найдено")
    if a.status == "Удалено":
        raise HTTPException(400, "Назначение удалено — сначала восстановите его")
    execs = db.query(Execution).filter(Execution.assignment_id == aid).all()
    busy = {e.planned_date for e in execs if e.status != "Запланировано"}
    removed = 0
    for e in execs:
        if e.status == "Запланировано":
            db.delete(e)
            removed += 1
    db.flush()
    schedule = generate_schedule(a.start_date, a.end_date, a.frequency)
    created = 0
    for d in schedule:
        if d in busy:
            continue
        db.add(Execution(
            id=new_id("EX"),
            assignment_id=a.id,
            object_id=a.object_id,
            work_type_id=a.work_type_id,
            planned_date=d,
            status="Запланировано",
        ))
        created += 1
    a.total_price = round((a.price_per_unit or 0) * len(schedule), 2)
    db.commit()
    return {"ok": True, "removed": removed, "created": created}
