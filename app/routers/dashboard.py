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
    """
    Напоминания о предстоящих регламентных работах:
    Интервалы из msg.cfg [triggers] (10, 7, 3, 1 дней до даты).
    С переносом даты напоминания на пятницу при попадании на выходные.
    Каждое напоминание снабжается емким инспекционным сообщением от активного ИИ (YandexGPT/GigaChat) или эксперта 123-ФЗ.
    """
    import configparser
    from pathlib import Path
    from datetime import timedelta
    from app.services.ai_service import generate_inspector_reminder_text, load_ai_config

    today = date.today()
    msg_cfg_path = Path(__file__).parent.parent.parent / "msg.cfg"
    trigger_days = [10, 7, 3, 1]

    if msg_cfg_path.exists():
        try:
            cfg = configparser.ConfigParser()
            cfg.read(str(msg_cfg_path), encoding="utf-8")
            if cfg.has_section("triggers") and "remind_days_before" in cfg["triggers"]:
                raw = cfg["triggers"]["remind_days_before"]
                parsed = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
                if parsed:
                    trigger_days = sorted(parsed, reverse=True)
        except Exception:
            pass

    max_horizon_days = max(trigger_days) if trigger_days else 14
    horizon_end = today + timedelta(days=max_horizon_days + 3)

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

    ai_cfg = load_ai_config()
    alert_items = []

    for e in items:
        days_until_planned = (e.planned_date - today).days

        # Проверяем каждое пороговое правило (например 10, 7, 3, 1)
        # Если хотя бы для одного порога наступила дата напоминания с учетом переноса выходных
        should_alert = False
        matched_remind_dt = e.planned_date
        matched_trigger_step = 0

        for interval in trigger_days:
            remind_dt = e.planned_date - timedelta(days=interval)
            # Перенос с выходных на пятницу
            if remind_dt.weekday() == 5:
                remind_dt -= timedelta(days=1)
            elif remind_dt.weekday() == 6:
                remind_dt -= timedelta(days=2)

            if remind_dt <= today and e.planned_date >= today:
                should_alert = True
                matched_remind_dt = remind_dt
                matched_trigger_step = interval
                break

        if should_alert:
            d_dict = exec_dict(e, db)
            d_dict["RemindDate"] = matched_remind_dt.isoformat()
            d_dict["DaysLeft"] = days_until_planned
            d_dict["TriggerStep"] = matched_trigger_step
            # Генерируем живое инспекционное предупреждение (YandexGPT / GigaChat / 123-ФЗ)
            d_dict["InspectorMessage"] = generate_inspector_reminder_text(d_dict, days_until_planned, ai_cfg)
            alert_items.append(d_dict)

    return {"ok": True, "data": alert_items}


