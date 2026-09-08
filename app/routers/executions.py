# -*- coding: utf-8 -*-
import uuid
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.execution import Execution

router = APIRouter()


class ExecutionIn(BaseModel):
    AssignmentId: str
    PlannedDate: str
    Notes: Optional[str] = ""


class ExecutionEdit(BaseModel):
    Status: Optional[str] = None
    ActualDate: Optional[str] = None
    PerformedBy: Optional[str] = None
    Notes: Optional[str] = None


class RescheduleIn(BaseModel):
    NewDate: str


class BatchDoneIn(BaseModel):
    ExecutionIds: List[str]
    ActualDate: Optional[str] = None
    PerformedBy: Optional[str] = ""


def new_id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"



def to_dict(e, db):
    obj = db.query(Object).filter(Object.id == e.object_id).first()
    work = db.query(WorkType).filter(WorkType.id == e.work_type_id).first()
    a = db.query(Assignment).filter(Assignment.id == e.assignment_id).first()
    assign_deleted = bool(a) and a.status == "Удалено"
    object_deleted = bool(obj) and obj.status == "Удалён"
    if assign_deleted:
        deleted_reason = a.reason or "Назначение удалено"
    elif object_deleted:
        deleted_reason = "Объект удалён"
    else:
        deleted_reason = ""
    return {
        "ID": e.id,
        "AssignmentId": e.assignment_id,
        "ObjectId": e.object_id,
        "ObjectName": obj.name if obj else "",
        "ObjectAddress": obj.address if obj else "",
        "WorkId": e.work_type_id,
        "WorkName": work.name if work else "",
        "WorkCode": work.code if work else "",
        "Frequency": a.frequency if a else "",
        "Price": a.price_per_unit if a else 0,
        "PlannedDate": e.planned_date.isoformat() if e.planned_date else None,
        "ActualDate": e.actual_date.isoformat() if e.actual_date else None,
        "Status": e.status,
        "PerformedBy": e.performed_by or "",
        "Notes": e.notes or "",
        "IsOverdue": e.status == "Запланировано" and bool(e.planned_date) and e.planned_date < date.today(),
        "IsDeleted": assign_deleted or object_deleted,
        "DeletedReason": deleted_reason,
        "AssignmentStatus": a.status if a else "",
    }


def base_query(db):
    return (
        db.query(Execution)
        .join(Assignment, Assignment.id == Execution.assignment_id)
        .join(Object, Object.id == Execution.object_id)
        .filter(Object.status != "Удалён")
    )


@router.get("/")
def list_executions(
    object_id: Optional[str] = None,
    work_id: Optional[str] = None,
    year: Optional[int] = None,
    month: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = base_query(db)
    if object_id:
        q = q.filter(Execution.object_id == object_id)
    if work_id:
        q = q.filter(Execution.work_type_id == work_id)
    if date_from:
        try:
            df = date.fromisoformat(date_from)
            q = q.filter(Execution.planned_date >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = date.fromisoformat(date_to)
            q = q.filter(Execution.planned_date <= dt)
        except ValueError:
            pass
    if not date_from and not date_to:
        if month and not year:
            year = date.today().year
        if year and month:
            q = q.filter(
                Execution.planned_date >= date(year, month, 1),
                Execution.planned_date < (date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)),
            )
        elif year:
            q = q.filter(
                Execution.planned_date >= date(year, 1, 1),
                Execution.planned_date <= date(year, 12, 31),
            )
    if status:
        q = q.filter(Execution.status == status)
    items = q.order_by(Execution.planned_date).all()
    return {"ok": True, "data": [to_dict(e, db) for e in items]}


@router.get("/by-date")
def by_date(date_str: str = Query(..., alias="date"), db: Session = Depends(get_db)):
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты (нужно ГГГГ-ММ-ДД)")
    items = base_query(db).filter(Execution.planned_date == d).order_by(Execution.id).all()
    return {"ok": True, "data": [to_dict(e, db) for e in items]}


@router.get("/{eid}")
def get_execution(eid: str, db: Session = Depends(get_db)):
    e = db.query(Execution).filter(Execution.id == eid).first()
    if not e:
        raise HTTPException(404, "Выполнение не найдено")
    return {"ok": True, "data": to_dict(e, db)}


@router.post("/")
def create_execution(data: ExecutionIn, db: Session = Depends(get_db)):
    a = db.query(Assignment).filter(Assignment.id == data.AssignmentId).first()
    if not a:
        raise HTTPException(404, "Назначение не найдено")
    try:
        d = date.fromisoformat(data.PlannedDate)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")
    e = Execution(
        id=new_id("EX"),
        assignment_id=a.id,
        object_id=a.object_id,
        work_type_id=a.work_type_id,
        planned_date=d,
        status="Запланировано",
        notes=data.Notes or "",
    )
    db.add(e)
    db.commit()
    return {"ok": True, "data": to_dict(e, db)}


def get_live_execution(eid, db):
    e = db.query(Execution).filter(Execution.id == eid).first()
    if not e:
        raise HTTPException(404, "Выполнение не найдено")
    a = db.query(Assignment).filter(Assignment.id == e.assignment_id).first()
    if a and a.status == "Удалено":
        raise HTTPException(409, "Назначение удалено. Сначала восстановите его из модалки дня.")
    return e


@router.post("/batch-done")
def batch_done(data: BatchDoneIn, db: Session = Depends(get_db)):
    if not data.ExecutionIds:
        raise HTTPException(400, "Не выбраны выполнения")
    actual = date.fromisoformat(data.ActualDate) if data.ActualDate else date.today()
    updated = 0
    for eid in data.ExecutionIds:
        e = db.query(Execution).filter(Execution.id == eid).first()
        if not e:
            continue
        a = db.query(Assignment).filter(Assignment.id == e.assignment_id).first()
        if a and a.status == "Удалено":
            continue
        e.status = "Выполнено"
        e.actual_date = actual
        if data.PerformedBy:
            e.performed_by = data.PerformedBy
        updated += 1
    db.commit()
    return {"ok": True, "updated": updated}


@router.post("/{eid}/done")
def mark_done(eid: str, data: ExecutionEdit, db: Session = Depends(get_db)):
    e = get_live_execution(eid, db)
    e.status = "Выполнено"
    e.actual_date = date.fromisoformat(data.ActualDate) if data.ActualDate else date.today()
    if data.PerformedBy is not None:
        e.performed_by = data.PerformedBy
    if data.Notes is not None:
        e.notes = data.Notes
    db.commit()
    return {"ok": True}



@router.post("/{eid}/reschedule")
def reschedule(eid: str, data: RescheduleIn, db: Session = Depends(get_db)):
    e = get_live_execution(eid, db)
    try:
        nd = date.fromisoformat(data.NewDate)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")
    e.planned_date = nd
    e.status = "Перенесено"
    e.actual_date = None
    db.commit()
    return {"ok": True}


@router.post("/{eid}/cancel")
def cancel(eid: str, db: Session = Depends(get_db)):
    e = get_live_execution(eid, db)
    e.status = "Отменено"
    e.actual_date = None
    db.commit()
    return {"ok": True}


@router.put("/{eid}")
def update_execution(eid: str, data: ExecutionEdit, db: Session = Depends(get_db)):
    e = get_live_execution(eid, db)
    if data.Status is not None:
        e.status = data.Status
        if data.Status == "Выполнено" and not e.actual_date:
            e.actual_date = date.today()
        if data.Status == "Запланировано":
            e.actual_date = None
    if data.ActualDate is not None:
        e.actual_date = date.fromisoformat(data.ActualDate) if data.ActualDate else None
    if data.PerformedBy is not None:
        e.performed_by = data.PerformedBy
    if data.Notes is not None:
        e.notes = data.Notes
    db.commit()
    return {"ok": True, "data": to_dict(e, db)}


@router.delete("/{eid}")
def delete_execution(eid: str, db: Session = Depends(get_db)):
    e = db.query(Execution).filter(Execution.id == eid).first()
    if not e:
        raise HTTPException(404, "Выполнение не найдено")
    db.delete(e)
    db.commit()
    return {"ok": True}
