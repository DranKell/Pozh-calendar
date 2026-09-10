# -*- coding: utf-8 -*-
"""
Модуль службы информирования и рассылки уведомлений (MAX Messenger и Email).
Конфигурация читается из msg.cfg.
"""
import configparser
import json
import logging
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("notifier")
MSG_CFG_PATH = Path(__file__).parent.parent.parent / "msg.cfg"


def load_notifier_config() -> Dict[str, Any]:
    cfg = configparser.ConfigParser()
    if MSG_CFG_PATH.exists():
        try:
            cfg.read(str(MSG_CFG_PATH), encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения msg.cfg для notifier: %s", e)

    max_sec = cfg["max_messenger"] if cfg.has_section("max_messenger") else {}
    email_sec = cfg["email"] if cfg.has_section("email") else {}
    triggers_sec = cfg["triggers"] if cfg.has_section("triggers") else {}

    return {
        "max": {
            "enabled": max_sec.getboolean("enabled", fallback=False),
            "api_url": max_sec.get("api_url", "https://platform-api2.max.ru").rstrip("/"),
            "bot_id": max_sec.get("bot_id", ""),
            "bot_token": max_sec.get("bot_token", ""),
            "default_chat_id": max_sec.get("default_chat_id", "5741854"),
            "alert_chat_ids": [x.strip() for x in max_sec.get("alert_chat_ids", "").split(",") if x.strip()],
            "timeout": max_sec.getint("request_timeout_seconds", fallback=10),
        },
        "email": {
            "enabled": email_sec.getboolean("enabled", fallback=False),
            "smtp_host": email_sec.get("smtp_host", ""),
            "smtp_port": email_sec.getint("smtp_port", fallback=465),
            "use_ssl": email_sec.getboolean("use_ssl", fallback=True),
            "smtp_user": email_sec.get("smtp_user", ""),
            "smtp_password": email_sec.get("smtp_password", ""),
            "from_email": email_sec.get("from_email", ""),
            "from_name": email_sec.get("from_name", "Календарь ТО"),
            "to_recipients": [x.strip() for x in email_sec.get("to_recipients", "").split(",") if x.strip()],
        },
        "triggers": {
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

    token = max_cfg.get("bot_token", "").strip()
    if not token or token == "your_max_bot_token_secret_here":
        return {"ok": False, "error": "Токен бота MAX не задан в msg.cfg [max_messenger]"}

    target = str(recipient_id or max_cfg.get("default_chat_id") or "5741854").strip()
    api_url = max_cfg.get("api_url", "https://platform-api2.max.ru")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    payload = {"text": text}
    req_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": token,
        "Content-Type": "application/json; charset=utf-8",
    }

    # В MAX API отправка пользователю идет через /messages?user_id=...
    endpoint = f"{api_url}/messages?user_id={target}"

    try:
        req = urllib.request.Request(endpoint, data=req_body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=max_cfg.get("timeout", 10), context=ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            mid = data.get("message", {}).get("body", {}).get("mid")
            return {"ok": True, "mid": mid, "data": data}
    except urllib.error.HTTPError as e:
        # Если не найден как user_id, пробуем как chat_id
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

