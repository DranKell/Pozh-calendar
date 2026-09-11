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

from app.models.invoice import Invoice

router = APIRouter()


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    today = date.today()
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    # Выполнения текущего месяца
    month_execs = db.query(Execution).filter(
        Execution.planned_date >= month_start,
        Execution.planned_date < month_end,
    ).all()

    # Справочник цен назначений для расчета выручки
    assign_ids = {e.assignment_id for e in month_execs if e.assignment_id}
    assigns_map = {}
    if assign_ids:
        rows = db.query(Assignment.id, Assignment.price_per_unit).filter(Assignment.id.in_(assign_ids)).all()
        assigns_map = {r[0]: (r[1] or 0.0) for r in rows}

    rev_planned = 0.0
    rev_actual = 0.0
    done_on_time = 0
    done_total = 0

    for e in month_execs:
        price = assigns_map.get(e.assignment_id, 0.0)
        rev_planned += price
        if e.status == "Выполнено":
            done_total += 1
            rev_actual += price
            # Если выполнено в срок или раньше срока
            if not e.actual_date or e.actual_date <= e.planned_date:
                done_on_time += 1

    rev_percent = round((rev_actual / rev_planned * 100), 1) if rev_planned > 0 else 0.0
    sla_percent = round((done_on_time / done_total * 100), 1) if done_total > 0 else (100.0 if not month_execs else 0.0)

    # Дебиторская задолженность по счетам (Invoice)
    all_invoices = db.query(Invoice).all()
    total_debt = 0.0
    debtor_objects_set = set()
    for inv in all_invoices:
        inv_debt = max(0.0, (inv.total or 0.0) - (inv.paid_amount or 0.0))
        if inv_debt > 0.01:
            total_debt += inv_debt
            if inv.object_id:
                debtor_objects_set.add(inv.object_id)

    overdue_count = db.query(Execution).filter(
        Execution.status == "Запланировано",
        Execution.planned_date < today,
    ).count()

    return {
        "ok": True,
        "data": {
            "ObjectsCount": db.query(Object).filter(Object.status != "Удалён").count(),
            "WorksCount": db.query(WorkType).count(),
            "AssignmentsCount": db.query(Assignment).filter(Assignment.status == "Активно").count(),
            "MonthTotal": len(month_execs),
            "MonthDone": done_total,
            "Overdue": overdue_count,
            # Новые показатели CEO & ПБ:
            "RevenuePlanned": round(rev_planned, 2),
            "RevenueActual": round(rev_actual, 2),
            "RevenuePercent": rev_percent,
            "SlaPercent": sla_percent,
            "DoneOnTime": done_on_time,
            "TotalDebt": round(total_debt, 2),
            "DebtorsCount": len(debtor_objects_set),
        },
    }


@router.get("/debtors")
def debtors(limit: int = 6, db: Session = Depends(get_db)):
    """Топ объектов с дебиторской задолженностью"""
    all_invoices = db.query(Invoice).order_by(Invoice.date.desc()).all()
    debt_by_obj = {}
    for inv in all_invoices:
        debt = max(0.0, (inv.total or 0.0) - (inv.paid_amount or 0.0))
        if debt > 0.01:
            if inv.object_id not in debt_by_obj:
                debt_by_obj[inv.object_id] = {
                    "ObjectId": inv.object_id,
                    "TotalDebt": 0.0,
                    "UnpaidInvoicesCount": 0,
                    "LatestInvoiceNumber": inv.number,
                    "LatestInvoiceDate": inv.date.isoformat() if inv.date else None,
                }
            debt_by_obj[inv.object_id]["TotalDebt"] += debt
            debt_by_obj[inv.object_id]["UnpaidInvoicesCount"] += 1

    sorted_debtors = sorted(debt_by_obj.values(), key=lambda x: x["TotalDebt"], reverse=True)[:limit]
    for d in sorted_debtors:
        obj = db.query(Object).filter(Object.id == d["ObjectId"]).first()
        d["ObjectName"] = obj.name if obj else "Неизвестный объект"
        d["ObjectAddress"] = obj.address if obj else ""
        d["ObjectInn"] = getattr(obj, "inn", "") if obj else ""
        d["TotalDebtFormatted"] = round(d["TotalDebt"], 2)

    return {"ok": True, "data": sorted_debtors}


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


