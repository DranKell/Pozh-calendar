# -*- coding: utf-8 -*-
"""
Модуль службы информирования и рассылки уведомлений (MAX Messenger и Email).
Конфигурация читается из msg.cfg.
"""
import configparser
import json
import logging
import smtplib
import ssl
import urllib.request
import urllib.error
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta

logger = logging.getLogger("notifier")
MSG_CFG_PATH = Path(__file__).parent.parent.parent / "msg.cfg"


def load_notifier_config() -> Dict[str, Any]:
    cfg = configparser.ConfigParser()
    if MSG_CFG_PATH.exists():
        try:
            cfg.read(str(MSG_CFG_PATH), encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения msg.cfg для notifier: %s", e)

    gen_sec = cfg["general"] if cfg.has_section("general") else {}
    max_sec = cfg["max_messenger"] if cfg.has_section("max_messenger") else {}
    email_sec = cfg["email"] if cfg.has_section("email") else {}
    triggers_sec = cfg["triggers"] if cfg.has_section("triggers") else {}

    raw_remind = triggers_sec.get("remind_days_before", "10, 7, 3, 1")
    parsed_remind = [int(x.strip()) for x in raw_remind.split(",") if x.strip().isdigit()]

    return {
        "general": {
            "enabled": gen_sec.getboolean("enabled", fallback=True),
            "subject_prefix": gen_sec.get("subject_prefix", "[Календарь ТО]"),
            "timezone": gen_sec.get("timezone", "Europe/Moscow"),
            "send_startup_ping": gen_sec.getboolean("send_startup_ping", fallback=False),
        },
        "max": {
            "enabled": max_sec.getboolean("enabled", fallback=False),
            "api_url": max_sec.get("api_url", "https://platform-api2.max.ru").rstrip("/"),
            "bot_id": max_sec.get("bot_id", ""),
            "bot_token": max_sec.get("bot_token", ""),
            "default_chat_id": max_sec.get("default_chat_id", "5741854"),
            "alert_chat_ids": [x.strip() for x in max_sec.get("alert_chat_ids", "").split(",") if x.strip()],
            "timeout": max_sec.getint("request_timeout_seconds", fallback=10),
            "verify_ssl": max_sec.getboolean("verify_ssl", fallback=True),
        },
        "email": {
            "enabled": email_sec.getboolean("enabled", fallback=False),
            "smtp_host": email_sec.get("smtp_host", "127.0.0.1"),
            "smtp_port": email_sec.getint("smtp_port", fallback=587),
            "use_ssl": email_sec.getboolean("use_ssl", fallback=False),
            "use_starttls": email_sec.getboolean("use_starttls", fallback=True),
            "require_auth": email_sec.getboolean("require_auth", fallback=True),
            "smtp_user": email_sec.get("smtp_user", ""),
            "smtp_password": email_sec.get("smtp_password", ""),
            "from_email": email_sec.get("from_email", ""),
            "from_name": email_sec.get("from_name", "Служба пожарной безопасности и ТО"),
            "reply_to": email_sec.get("reply_to", ""),
            "to_recipients": [x.strip() for x in email_sec.get("to_recipients", "").split(",") if x.strip()],
            "cc_recipients": [x.strip() for x in email_sec.get("cc_recipients", "").split(",") if x.strip()],
            "bcc_recipients": [x.strip() for x in email_sec.get("bcc_recipients", "").split(",") if x.strip()],
            "timeout": email_sec.getint("timeout_seconds", fallback=15),
        },
        "triggers": {
            "remind_days_before": parsed_remind if parsed_remind else [10, 7, 3, 1],
            "daily_digest_time": triggers_sec.get("daily_digest_time", "08:30"),
            "notify_on_overdue": triggers_sec.getboolean("notify_on_overdue", fallback=True),
            "notify_on_invoice_created": triggers_sec.getboolean("notify_on_invoice_created", fallback=True),
            "notify_on_invoice_paid": triggers_sec.getboolean("notify_on_invoice_paid", fallback=True),
        }
    }


def send_max_message(text: str, recipient_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Отправка сообщения пользователю или в чат через MAX Bot API.
    Поддерживает прямую отправку по user_id или chat_id.
    """
    config = load_notifier_config()
    max_cfg = config.get("max", {})

    if not max_cfg.get("enabled", False):
        return {"ok": False, "error": "Оповещения в MAX отключены в msg.cfg [max_messenger]"}

    token = max_cfg.get("bot_token", "").strip()
    if not token or token in ("your_max_bot_token_secret_here", "ВАШ_ДЕЙСТВУЮЩИЙ_ТОКЕН_БОТА_MAX"):
        return {"ok": False, "error": "Токен бота MAX не задан или содержит шаблонное значение в msg.cfg [max_messenger]"}

    target = str(recipient_id or max_cfg.get("default_chat_id") or "5741854").strip()
    api_url = max_cfg.get("api_url", "https://platform-api2.max.ru")

    ctx = ssl.create_default_context()
    if not max_cfg.get("verify_ssl", True):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    payload = {"text": text}
    req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": token,
        "Content-Type": "application/json; charset=utf-8",
    }

    endpoint_user = f"{api_url}/messages?user_id={target}"

    try:
        req = urllib.request.Request(endpoint_user, data=req_body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=max_cfg.get("timeout", 10), context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            mid = data.get("message", {}).get("body", {}).get("mid")
            return {"ok": True, "mid": mid, "data": data}
    except urllib.error.HTTPError as e:
        # Пробуем как chat_id
        try:
            endpoint_chat = f"{api_url}/messages?chat_id={target}"
            req_chat = urllib.request.Request(endpoint_chat, data=req_body, headers=headers, method="POST")
            with urllib.request.urlopen(req_chat, timeout=max_cfg.get("timeout", 10), context=ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                mid = data.get("message", {}).get("body", {}).get("mid")
                return {"ok": True, "mid": mid, "data": data}
        except Exception:
            pass

        err_body = e.read().decode("utf-8", errors="replace")
        logger.error("Ошибка HTTP при отправке в MAX (%s): %s %s", target, e.code, err_body)
        return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        logger.error("Сетевая ошибка при отправке в MAX: %s", e)
        return {"ok": False, "error": str(e)}


def send_email_message(
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    to_recipients: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Отправка электронного письма через SMTP (подходит для локального Mailcow, внешних SMTP).
    """
    config = load_notifier_config()
    email_cfg = config.get("email", {})
    gen_cfg = config.get("general", {})

    if not email_cfg.get("enabled", False):
        return {"ok": False, "error": "Отправка почты отключена в msg.cfg [email]"}

    host = email_cfg.get("smtp_host", "").strip()
    if not host or host == "smtp.example.com":
        return {"ok": False, "error": "Адрес SMTP-сервера не задан в msg.cfg [email]"}

    port = int(email_cfg.get("smtp_port", 587))
    use_ssl = email_cfg.get("use_ssl", False)
    use_starttls = email_cfg.get("use_starttls", True)
    require_auth = email_cfg.get("require_auth", True)
    user = email_cfg.get("smtp_user", "").strip()
    password = email_cfg.get("smtp_password", "").strip()
    from_email = email_cfg.get("from_email", user) or user
    from_name = email_cfg.get("from_name", "Календарь ТО")
    reply_to = email_cfg.get("reply_to", "")
    timeout = email_cfg.get("timeout", 15)

    recipients = to_recipients or email_cfg.get("to_recipients", [])
    cc_list = email_cfg.get("cc_recipients", [])
    bcc_list = email_cfg.get("bcc_recipients", [])

    if not recipients and not bcc_list:
        return {"ok": False, "error": "Не указаны получатели (to_recipients) в msg.cfg [email]"}

    prefix = gen_cfg.get("subject_prefix", "[Календарь ТО]").strip()
    full_subject = f"{prefix} {subject}" if prefix else subject

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(full_subject, "utf-8")
    msg["From"] = f"{Header(from_name, 'utf-8').encode()} <{from_email}>"
    msg["To"] = ", ".join(recipients)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0300")

    part_text = MIMEText(text_content, "plain", "utf-8")
    msg.attach(part_text)

    if html_content:
        part_html = MIMEText(html_content, "html", "utf-8")
        msg.attach(part_html)
    else:
        # Автоматическая простая HTML-версия из текста
        escaped_html = (
            text_content.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        html_body = f"""<html>
<body style="font-family: Arial, sans-serif; color: #1e293b; line-height: 1.6; padding: 20px;">
  <div style="max-width: 650px; margin: auto; border: 1px solid #e2e8f0; border-radius: 8px; padding: 24px; background: #ffffff;">
    <h2 style="color: #0284c7; margin-top: 0;">{Header(full_subject, 'utf-8').decode()}</h2>
    <div style="font-size: 14px; background: #f8fafc; border-left: 4px solid #0284c7; padding: 12px; margin: 15px 0;">
      {escaped_html}
    </div>
    <div style="font-size: 12px; color: #64748b; margin-top: 20px; border-top: 1px solid #e2e8f0; padding-top: 10px;">
      Автоматическое уведомление системы «Календарь ТО». Пожалуйста, не отвечайте на это письмо.
    </div>
  </div>
</body>
</html>"""
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    all_targets = list(set(recipients + cc_list + bcc_list))

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)

        server.ehlo()
        if not use_ssl and use_starttls:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            server.starttls(context=context)
            server.ehlo()

        if require_auth and user:
            server.login(user, password)

        server.sendmail(from_email, all_targets, msg.as_string())
        server.quit()
        logger.info("Уведомление успешно отправлено по Email на %s", all_targets)
        return {"ok": True, "recipients": all_targets}
    except Exception as e:
        logger.error("Ошибка при отправке письма через SMTP (%s:%s): %s", host, port, e)
        return {"ok": False, "error": str(e)}


def format_single_execution_message(exec_item: Dict[str, Any], days_left: int) -> str:
    """Форматирование индивидуального сообщения, когда запланирован ровно 1 объект"""
    obj_name = exec_item.get("ObjectName") or "Объект защиты"
    work_code = exec_item.get("WorkCode") or "ПБ"
    work_name = exec_item.get("WorkName") or "Регламентное ТО"
    planned_dt = exec_item.get("PlannedDate") or ""
    inspector_text = exec_item.get("InspectorMessage") or ""

    if days_left == 1:
        time_str = "1 день (ЗАВТРА)"
    elif days_left == 0:
        time_str = "СЕГОДНЯ"
    elif days_left in (2, 3, 4):
        time_str = f"{days_left} дня"
    else:
        time_str = f"{days_left} дней"

    addr = exec_item.get("ObjectAddress") or exec_item.get("Address") or ""
    lines = [
        "🚨 ПЛАНОВОЕ ОПОВЕЩЕНИЕ СЛУЖБЫ ПОЖАРНОЙ БЕЗОПАСНОСТИ",
        "",
        f"🏢 Объект: {obj_name}",
    ]
    if addr:
        lines.append(f"📍 Адрес: {addr}")
    lines.extend([
        f"🔧 Регламент: {work_code} — {work_name}",
        f"📅 Дата проведения: {planned_dt} (осталось: {time_str})",
        "📋 Нормативная база: п. 54 ППР РФ № 1479, СП 484.1311500",
    ])
    if inspector_text:
        lines.append("")
        lines.append(inspector_text)

    lines.extend([
        "",
        "---",
        "Автоматизированный комплекс «Календарь ТО»"
    ])
    return "\n".join(lines)


def format_grouped_digest_message(items: List[Dict[str, Any]], days_left: int) -> str:
    """
    Группировка нескольких объектов (от 2 и более) в ЕДИНОЕ сводное сообщение,
    исключающее спам и спасающее от ограничений антифлуда Bot API.
    """
    if days_left == 1:
        time_header = "ЗАВТРА (остался 1 день)"
    elif days_left == 0:
        time_header = "СЕГОДНЯ"
    elif days_left in (2, 3, 4):
        time_header = f"через {days_left} дня"
    else:
        time_header = f"через {days_left} дней"

    planned_date = items[0].get("PlannedDate") or ""

    lines = [
        f"📋 СВОДНЫЙ ПЛАН ТО НА {planned_date} ({time_header})",
        f"Всего объектов в графике: {len(items)}",
        "",
    ]

    for idx, it in enumerate(items, 1):
        obj_name = it.get("ObjectName") or "Объект"
        addr = it.get("ObjectAddress") or it.get("Address") or ""
        addr_str = f" ({addr})" if addr else ""
        work_code = it.get("WorkCode") or "ПБ"
        work_name = it.get("WorkName") or "Регламент"
        contact = it.get("ContactPerson") or ""
        phone = it.get("Phone") or ""
        contact_str = f" | Контакт: {contact} ({phone})" if contact or phone else ""

        lines.append(f"{idx}. {obj_name}{addr_str}")
        lines.append(f"   🔧 {work_code} — {work_name}{contact_str}")
        lines.append("")

    lines.extend([
        "⚠️ Требование Госпожнадзора:",
        "Обеспечьте наличие нарядов-допусков у дежурных бригад и внесение обязательных записей в журналы эксплуатации систем противопожарной защиты (п. 54 ППР РФ № 1479).",
        "",
        "---",
        "Автоматизированный комплекс «Календарь ТО»"
    ])

    return "\n".join(lines)


def send_reminders_batch(items: List[Dict[str, Any]], days_left: int, recipient_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Умная диспетчеризация:
    - если 1 объект -> персональная карточка;
    - если 2 и более объектов -> ЕДИНОЕ компактное сводное сообщение.
    """
    if not items:
        return {"ok": False, "error": "Список напоминаний пуст"}

    if len(items) == 1:
        text = format_single_execution_message(items[0], days_left)
    else:
        text = format_grouped_digest_message(items, days_left)

    return send_max_message(text, recipient_id=recipient_id)


def broadcast_notification(subject: str, message_text: str) -> Dict[str, Any]:
    """
    Широковещательная рассылка одновременно во все активные каналы:
    - Мессенджер MAX (в default_chat_id и alert_chat_ids)
    - Почта Email (всем to_recipients, cc, bcc)
    """
    config = load_notifier_config()
    max_cfg = config.get("max", {})
    email_cfg = config.get("email", {})

    results = {
        "max": {"attempted": False, "ok": False},
        "email": {"attempted": False, "ok": False},
    }

    # 1. Отправка в MAX
    if max_cfg.get("enabled"):
        results["max"]["attempted"] = True
        targets = set()
        if max_cfg.get("default_chat_id"):
            targets.add(str(max_cfg.get("default_chat_id")))
        for c in max_cfg.get("alert_chat_ids", []):
            if c:
                targets.add(str(c))

        max_ok = True
        max_errors = []
        for chat_id in targets:
            res = send_max_message(message_text, recipient_id=chat_id)
            if not res.get("ok"):
                max_ok = False
                max_errors.append(f"{chat_id}: {res.get('error')}")

        results["max"]["ok"] = max_ok
        if not max_ok:
            results["max"]["error"] = "; ".join(max_errors)

    # 2. Отправка по Email
    if email_cfg.get("enabled"):
        results["email"]["attempted"] = True
        res_email = send_email_message(subject=subject, text_content=message_text)
        results["email"]["ok"] = res_email.get("ok", False)
        if not res_email.get("ok"):
            results["email"]["error"] = res_email.get("error")

    return results


def check_and_send_scheduled_reminders(db_session_factory) -> Dict[str, Any]:
    """
    Фоновая проверка сроков ТО: вычисляет напоминания за 10, 7, 3, 1 дней с учётом выходных
    и рассылает их по MAX и Email.
    """
    from app.models.object import Object
    from app.models.assignment import Assignment
    from app.models.execution import Execution
    from app.routers.executions import to_dict as exec_dict
    from app.services.ai_service import generate_inspector_reminder_text, load_ai_config

    config = load_notifier_config()
    if not config["general"].get("enabled", True):
        return {"ok": False, "reason": "Уведомления отключены в [general] msg.cfg"}

    trigger_days = config["triggers"].get("remind_days_before", [10, 7, 3, 1])
    today = date.today()
    max_h = max(trigger_days) if trigger_days else 14
    horizon_end = today + timedelta(days=max_h + 3)

    db = db_session_factory()
    try:
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
        grouped_by_day: Dict[int, List[Dict[str, Any]]] = {}

        for e in items:
            days_until_planned = (e.planned_date - today).days

            for interval in trigger_days:
                remind_dt = e.planned_date - timedelta(days=interval)
                # Перенос с выходных на пятницу
                if remind_dt.weekday() == 5:
                    remind_dt -= timedelta(days=1)
                elif remind_dt.weekday() == 6:
                    remind_dt -= timedelta(days=2)

                if remind_dt == today:
                    d_dict = exec_dict(e, db)
                    d_dict["RemindDate"] = remind_dt.isoformat()
                    d_dict["DaysLeft"] = days_until_planned
                    d_dict["TriggerStep"] = interval
                    d_dict["InspectorMessage"] = generate_inspector_reminder_text(d_dict, days_until_planned, ai_cfg)
                    grouped_by_day.setdefault(days_until_planned, []).append(d_dict)
                    break

        sent_reports = []
        for days_left, day_items in grouped_by_day.items():
            if len(day_items) == 1:
                text = format_single_execution_message(day_items[0], days_left)
                subj = f"Плановое ТО: {day_items[0].get('ObjectName')} ({days_left} дн.)"
            else:
                text = format_grouped_digest_message(day_items, days_left)
                subj = f"Сводный план ТО: {len(day_items)} объектов (через {days_left} дн.)"

            b_res = broadcast_notification(subject=subj, message_text=text)
            sent_reports.append({"days_left": days_left, "count": len(day_items), "result": b_res})

        return {"ok": True, "sent_groups": len(sent_reports), "reports": sent_reports}
    finally:
        db.close()


