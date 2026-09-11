# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import CONFIG

router = APIRouter()
CONFIG_PATH = Path(__file__).parent.parent.parent / "config.json"


class CompanyIn(BaseModel):
    name: Optional[str] = ""
    inn: Optional[str] = ""
    kpp: Optional[str] = ""
    ogrn: Optional[str] = ""
    address: Optional[str] = ""
    phone: Optional[str] = ""
    email: Optional[str] = ""
    bank: Optional[str] = ""
    bik: Optional[str] = ""
    account: Optional[str] = ""
    corrAccount: Optional[str] = ""
    director: Optional[str] = ""
    accountant: Optional[str] = ""
    invoicePrefix: Optional[str] = "СЧ"
    vatRate: Optional[float] = 0


@router.get("/company")
def get_company():
    return {"ok": True, "data": CONFIG.get("company", {}) if isinstance(CONFIG, dict) else {}}


@router.put("/company")
def put_company(data: CompanyIn):
    try:
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"Не удалось прочитать config.json: {exc}")

    company = cfg.get("company", {})
    if hasattr(data, "model_dump"):
        update = data.model_dump(exclude_none=True)
    else:
        update = data.dict(exclude_none=True)

    company.update(update)
    cfg["company"] = company

    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    if isinstance(CONFIG, dict):
        CONFIG.clear()
        CONFIG.update(cfg)

    return {"ok": True, "data": company}


class TestNotifyRequest(BaseModel):
    channel: Optional[str] = "all"  # 'all', 'email', 'max'
    customEmail: Optional[str] = None
    customChatId: Optional[str] = None
    text: Optional[str] = None


@router.post("/test-notify")
def test_notify(req: TestNotifyRequest):
    """
    Тестовая отправка уведомления для проверки каналов связи (MAX Bot и Mailcow SMTP).
    """
    from app.services.notifier import send_max_message, send_email_message, broadcast_notification

    test_text = req.text or "🔔 Тестовое оповещение из Календаря ТО: каналы оповещения настроены успешно!"
    subject = "Тестовое оповещение системы ТО"
    results = {}

    if req.channel in ("all", "max"):
        results["max"] = send_max_message(test_text, recipient_id=req.customChatId)

    if req.channel in ("all", "email"):
        recipients = [req.customEmail] if req.customEmail else None
        results["email"] = send_email_message(subject=subject, text_content=test_text, to_recipients=recipients)

    return {"ok": True, "results": results}


@router.post("/check-reminders")
def trigger_check_reminders():
    """
    Принудительный запуск проверки и отправки регламентных напоминаний за 10, 7, 3, 1 дней.
    """
    from app.db.session import SessionLocal
    from app.services.notifier import check_and_send_scheduled_reminders

    res = check_and_send_scheduled_reminders(SessionLocal)
    return {"ok": True, "details": res}

