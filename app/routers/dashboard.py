# -*- coding: utf-8 -*-
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.execution import Execution
from app.routers.executions import to_dict as exec_dict

router = APIRouter()


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)
    month_execs = db.query(Execution).filter(
        Execution.planned_date >= month_start,
        Execution.planned_date < month_end,
    ).all()
    return {
        "ok": True,
        "data": {
            "ObjectsCount": db.query(Object).filter(Object.status != "Удалён").count(),
            "WorksCount": db.query(WorkType).count(),
            "AssignmentsCount": db.query(Assignment).filter(Assignment.status == "Активно").count(),
            "MonthTotal": len(month_execs),
            "MonthDone": sum(1 for e in month_execs if e.status == "Выполнено"),
            "Overdue": db.query(Execution).filter(
                Execution.status == "Запланировано",
                Execution.planned_date < today,
            ).count(),
        },
    }


@router.get("/upcoming")
def upcoming(limit: int = 8, db: Session = Depends(get_db)):
    today = date.today()
    items = (
        db.query(Execution)
        .filter(Execution.planned_date >= today, Execution.status == "Запланировано")
        .order_by(Execution.planned_date)
        .limit(limit)
        .all()
    )
    return {"ok": True, "data": [exec_dict(e, db) for e in items]}


@router.get("/overdue")
def overdue(limit: int = 8, db: Session = Depends(get_db)):
    today = date.today()
    items = (
        db.query(Execution)
        .filter(Execution.status == "Запланировано", Execution.planned_date < today)
        .order_by(Execution.planned_date)
        .limit(limit)
        .all()
    )
    return {"ok": True, "data": [exec_dict(e, db) for e in items]}


@router.get("/reminders")
def reminders(db: Session = Depends(get_db)):
    """Напоминания о предстоящих работах: за 7 дней (если выпадает на сб/вс — перенос на пятницу)."""
    from datetime import timedelta
    today = date.today()
    # Ищем предстоящие работы в горизонте до 14 дней
    horizon_end = today + timedelta(days=14)
    items = (
        db.query(Execution)
        .join(Assignment, Assignment.id == Execution.assignment_id)
        .join(Object, Object.id == Execution.object_id)
        .filter(
            Execution.status == "Запланировано",
            Object.status != "Удалён",
            Assignment.status == "Активно",
            Execution.planned_date >= today,
            Execution.planned_date <= horizon_end,
        )
        .order_by(Execution.planned_date)
        .all()
    )

    alert_items = []
    for e in items:
        # Дата напоминания: за 7 дней до планового выполнения
        remind_dt = e.planned_date - timedelta(days=7)
        # Если дата напоминания выпадает на сб (weekday=5) -> перенос на пт (-1 день)
        if remind_dt.weekday() == 5:
            remind_dt -= timedelta(days=1)
        # Если на вс (weekday=6) -> перенос на пт (-2 дня)
        elif remind_dt.weekday() == 6:
            remind_dt -= timedelta(days=2)

        # Если дата напоминания уже наступила (сегодня или ранее), но работа ещё в будущем
        if remind_dt <= today and e.planned_date >= today:
            d_dict = exec_dict(e, db)
            days_left = (e.planned_date - today).days
            d_dict["RemindDate"] = remind_dt.isoformat()
            d_dict["DaysLeft"] = days_left
            alert_items.append(d_dict)

    return {"ok": True, "data": alert_items}

