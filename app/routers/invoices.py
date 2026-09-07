# -*- coding: utf-8 -*-
import html
import random
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.invoice import Invoice, InvoiceItem
from app.models.company import Company
from app.config import CONFIG

router = APIRouter()
STATIC_DIR = Path(__file__).parent.parent / "static"


class InvoiceItemIn(BaseModel):
    AssignmentId: Optional[str] = None
    Name: Optional[str] = ""
    Description: Optional[str] = ""
    Quantity: Optional[float] = 1
    Unit: Optional[str] = "усл."
    Price: Optional[float] = 0


class InvoiceCreate(BaseModel):
    ObjectId: str
    CompanyId: Optional[str] = None
    AssignmentIds: Optional[List[str]] = []
    Items: Optional[List[InvoiceItemIn]] = []
    IncludeAllDebt: Optional[bool] = False
    Date: Optional[str] = None
    DueDate: Optional[str] = None
    VatRate: Optional[float] = 0
    Notes: Optional[str] = ""


class PayIn(BaseModel):
    Amount: Optional[float] = None
    PaidDate: Optional[str] = None
    PaymentRef: Optional[str] = ""


def get_company(db: Optional[Session] = None, company_id: Optional[str] = None) -> dict:
    if db:
        if company_id:
            c = db.query(Company).filter(Company.id == company_id).first()
            if c:
                return {
                    "id": c.id,
                    "name": c.name,
                    "inn": c.inn or "",
                    "kpp": c.kpp or "",
                    "ogrn": c.ogrn or "",
                    "address": c.address or "",
                    "phone": c.phone or "",
                    "email": c.email or "",
                    "bank": c.bank or "",
                    "bik": c.bik or "",
                    "account": c.account or "",
                    "corrAccount": c.corr_account or "",
                    "director": c.director or "",
                    "accountant": c.accountant or "",
                    "invoicePrefix": c.invoice_prefix or "СЧ",
                    "vatRate": c.vat_rate or 0.0,
                    "isDefault": c.is_default,
                }
        default_c = db.query(Company).filter(Company.is_default == True).first()
        if not default_c:
            default_c = db.query(Company).first()
        if default_c:
            return {
                "id": default_c.id,
                "name": default_c.name,
                "inn": default_c.inn or "",
                "kpp": default_c.kpp or "",
                "ogrn": default_c.ogrn or "",
                "address": default_c.address or "",
                "phone": default_c.phone or "",
                "email": default_c.email or "",
                "bank": default_c.bank or "",
                "bik": default_c.bik or "",
                "account": default_c.account or "",
                "corrAccount": default_c.corr_account or "",
                "director": default_c.director or "",
                "accountant": default_c.accountant or "",
                "invoicePrefix": default_c.invoice_prefix or "СЧ",
                "vatRate": default_c.vat_rate or 0.0,
                "isDefault": default_c.is_default,
            }
    return CONFIG.get("company", {}) if isinstance(CONFIG, dict) else {}


def add_business_days(start, days):
    current = start
    added = 0
    while added < days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added += 1
    return current


def next_number(db, company_dict_data: Optional[dict] = None):
    prefix = ((company_dict_data or {}).get("invoicePrefix") or get_company(db).get("invoicePrefix") or "СЧ").strip() or "СЧ"
    year = date.today().year
    like = f"{prefix}-{year}-"
    rows = db.query(Invoice).filter(Invoice.number.like(like + "%")).all()
    seq = 0
    for row in rows:
        try:
            n = int(row.number.rsplit("-", 1)[-1])
            if n > seq:
                seq = n
        except Exception:
            pass
    return f"{prefix}-{year}-{seq + 1:04d}"


def money(n):
    return "{:,.2f}".format(float(n or 0)).replace(",", " ") + " ₽"


def esc(s):
    return html.escape(str(s or ""))


def fmt_date(d):
    return d.strftime("%d.%m.%Y") if d else ""


def compute_status(inv):
    status = inv.status
    debt = max(0.0, (inv.total or 0) - (inv.paid_amount or 0))
    if status in ("Выставлен", "Частично") and inv.due_date and inv.due_date < date.today() and debt > 0:
        return "Просрочен"
    return status


def inv_dict(inv, db):
    obj = db.query(Object).filter(Object.id == inv.object_id).first()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).order_by(InvoiceItem.id).all()
    comp = get_company(db, getattr(inv, "company_id", None))
    return {
        "ID": inv.id,
        "Number": inv.number,
        "Date": inv.date.isoformat() if inv.date else None,
        "DueDate": inv.due_date.isoformat() if inv.due_date else None,
        "ObjectId": inv.object_id,
        "ObjectName": obj.name if obj else "",
        "ObjectInn": getattr(obj, "inn", "") if obj else "",
        "ObjectAddress": obj.address if obj else "",
        "CompanyId": getattr(inv, "company_id", None) or comp.get("id"),
        "CompanyName": comp.get("name") or "",
        "CompanyInn": comp.get("inn") or "",
        "Status": compute_status(inv),
        "Subtotal": inv.subtotal or 0,
        "VatRate": inv.vat_rate or 0,
        "VatAmount": inv.vat_amount or 0,
        "Total": inv.total or 0,
        "PaidAmount": inv.paid_amount or 0,
        "Debt": max(0.0, (inv.total or 0) - (inv.paid_amount or 0)),
        "PaidDate": inv.paid_date.isoformat() if inv.paid_date else None,
        "PaymentRef": inv.payment_ref or "",
        "PaymentPurpose": inv.payment_purpose or "",
        "Notes": inv.notes or "",
        "Items": [{
            "ID": it.id,
            "AssignmentId": it.assignment_id,
            "Name": it.name,
            "Description": it.description or "",
            "Quantity": it.quantity or 1,
            "Unit": it.unit or "усл.",
            "Price": it.price or 0,
            "Amount": it.amount or 0,
        } for it in items],
    }


@router.get("/")
def list_invoices(object_id: Optional[str] = None, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Invoice)
    if object_id:
        q = q.filter(Invoice.object_id == object_id)
    rows = q.order_by(Invoice.date.desc(), Invoice.created_at.desc()).all()
    result = [inv_dict(r, db) for r in rows]
    if status:
        result = [x for x in result if x["Status"] == status]
    return {"ok": True, "data": result}


@router.post("/")
def create_invoice(data: InvoiceCreate, db: Session = Depends(get_db)):
    obj = db.query(Object).filter(Object.id == data.ObjectId).first()
    if not obj:
        raise HTTPException(404, "Объект не найден")
    if getattr(obj, "status", "") == "Удалён":
        raise HTTPException(400, "Объект удалён")

    comp = get_company(db, data.CompanyId)
    if not comp.get("name") or not comp.get("inn"):
        raise HTTPException(400, "Заполните реквизиты своей организации: Счета → Наши реквизиты")

    try:
        inv_date = date.fromisoformat(data.Date) if data.Date else date.today()
        due_date = date.fromisoformat(data.DueDate) if data.DueDate else add_business_days(inv_date, 5)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")

    vat_rate = float(data.VatRate or 0)
    lines = []

    if data.IncludeAllDebt:
        assigns = db.query(Assignment).filter(Assignment.object_id == obj.id, Assignment.status != "Удалено").all()
        for a in assigns:
            debt = max(0.0, (a.total_price or 0) - (getattr(a, "paid_amount", 0) or 0))
            if debt > 0:
                work = db.query(WorkType).filter(WorkType.id == a.work_type_id).first()
                name = (work.code + " — " + work.name) if work else "Услуга"
                desc = f"{a.frequency}, период {a.start_date.isoformat() if a.start_date else ''} — {a.end_date.isoformat() if a.end_date else ''}"
                lines.append((a, a.work_type_id, name, desc, 1.0, "усл.", round(debt, 2), round(debt, 2)))

    elif data.AssignmentIds:
        for aid in data.AssignmentIds:
            a = db.query(Assignment).filter(Assignment.id == aid, Assignment.object_id == obj.id).first()
            if not a:
                continue
            debt = max(0.0, (a.total_price or 0) - (getattr(a, "paid_amount", 0) or 0))
            if debt <= 0:
                continue
            work = db.query(WorkType).filter(WorkType.id == a.work_type_id).first()
            name = (work.code + " — " + work.name) if work else "Услуга"
            desc = f"{a.frequency}, период {a.start_date.isoformat() if a.start_date else ''} — {a.end_date.isoformat() if a.end_date else ''}"
            lines.append((a, a.work_type_id, name, desc, 1.0, "усл.", round(debt, 2), round(debt, 2)))

    elif data.Items:
        for it in data.Items:
            if not it.Name or (it.Price or 0) <= 0:
                continue
            qty = float(it.Quantity or 1)
            price = float(it.Price or 0)
            amount = round(qty * price, 2)
            lines.append((None, None, it.Name, it.Description or "", qty, it.Unit or "усл.", price, amount))

    if not lines:
        raise HTTPException(400, "Нет позиций для счёта: нет долга по назначениям или не выбраны услуги")

    number = next_number(db, comp)
    inv = Invoice(
        id=f"INV-{uuid.uuid4().hex[:8]}",
        number=number,
        date=inv_date,
        due_date=due_date,
        object_id=obj.id,
        company_id=comp.get("id"),
        status="Выставлен",
        subtotal=0.0,
        vat_rate=vat_rate,
        vat_amount=0.0,
        total=0.0,
        paid_amount=0.0,
        payment_purpose=f"Оплата по счёту {number} от {fmt_date(inv_date)} за техническое обслуживание ({obj.name})",
        notes=data.Notes or "",
    )
    db.add(inv)
    db.flush()

    subtotal = 0.0
    for assignment, work_id, name, desc, qty, unit, price, amount in lines:
        db.add(InvoiceItem(
            id=f"INVITM-{uuid.uuid4().hex[:8]}",
            invoice_id=inv.id,
            assignment_id=assignment.id if assignment else None,
            work_type_id=work_id,
            name=name,
            description=desc,
            quantity=qty,
            unit=unit,
            price=price,
            amount=amount,
        ))
        subtotal += amount

    subtotal = round(subtotal, 2)
    vat_amount = round(subtotal * vat_rate / 100.0, 2) if vat_rate else 0.0
    total = round(subtotal + vat_amount, 2)

    inv.subtotal = subtotal
    inv.vat_amount = vat_amount
    inv.total = total

    db.commit()
    return {"ok": True, "data": inv_dict(inv, db)}


@router.get("/{iid}")
def get_invoice(iid: str, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == iid).first()
    if not inv:
        raise HTTPException(404, "Счёт не найден")
    return {"ok": True, "data": inv_dict(inv, db)}


@router.post("/{iid}/pay")
def pay_invoice(iid: str, data: PayIn, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == iid).first()
    if not inv:
        raise HTTPException(404, "Счёт не найден")
    if inv.status == "Отменён":
        raise HTTPException(400, "Счёт отменён")

    remaining = max(0.0, (inv.total or 0) - (inv.paid_amount or 0))
    amount = float(data.Amount) if data.Amount is not None else remaining

    if amount <= 0:
        raise HTTPException(400, "Счёт уже оплачен")
    if amount > remaining + 0.01:
        raise HTTPException(400, f"Сумма превышает остаток по счёту ({money(remaining)})")

    inv.paid_amount = round((inv.paid_amount or 0) + amount, 2)
    inv.paid_date = date.fromisoformat(data.PaidDate) if data.PaidDate else date.today()
    if data.PaymentRef:
        inv.payment_ref = data.PaymentRef

    # Распределяем оплату по назначениям (без НДС, пропорционально позициям)
    if inv.subtotal and inv.subtotal > 0 and inv.total and inv.total > 0:
        payment_excl_vat = amount * inv.subtotal / inv.total
        items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).all()
        for it in items:
            if not it.assignment_id:
                continue
            alloc = payment_excl_vat * ((it.amount or 0) / inv.subtotal)
            a = db.query(Assignment).filter(Assignment.id == it.assignment_id).first()
            if a:
                current = getattr(a, "paid_amount", 0) or 0
                a.paid_amount = round(min((a.total_price or 0), current + alloc), 2)

    if (inv.paid_amount or 0) >= (inv.total or 0) - 0.01:
        inv.status = "Оплачен"
    else:
        inv.status = "Частично"

    db.commit()
    return {"ok": True, "data": inv_dict(inv, db)}


@router.post("/{iid}/cancel")
def cancel_invoice(iid: str, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == iid).first()
    if not inv:
        raise HTTPException(404, "Счёт не найден")
    if (inv.paid_amount or 0) > 0:
        raise HTTPException(400, "Нельзя отменить счёт с проведенной оплатой")
    inv.status = "Отменён"
    db.commit()
    return {"ok": True, "data": inv_dict(inv, db)}


@router.delete("/{iid}")
def delete_invoice(iid: str, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == iid).first()
    if not inv:
        raise HTTPException(404, "Счёт не найден")
    if (inv.paid_amount or 0) > 0:
        raise HTTPException(400, "Нельзя удалить счёт с проведенной оплатой")
    db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).delete()
    db.delete(inv)
    db.commit()
    return {"ok": True}


@router.get("/{iid}/print", response_class=HTMLResponse)
def print_invoice(iid: str, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == iid).first()
    if not inv:
        raise HTTPException(404, "Счёт не найден")

    obj = db.query(Object).filter(Object.id == inv.object_id).first()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).order_by(InvoiceItem.id).all()
    comp = get_company(db, getattr(inv, "company_id", None))

    logo_html = ""
    if (STATIC_DIR / "logo.png").exists():
        logo_html = '<img src="/static/logo.png" class="logo" alt="logo">'

    rows_html = ""
    for idx, it in enumerate(items, 1):
        desc_html = f'<div class="desc">{esc(it.description)}</div>' if it.description else ""
        rows_html += (
            "<tr>"
            f'<td class="center">{idx}</td>'
            f"<td>{esc(it.name)}{desc_html}</td>"
            f'<td class="num">{("{:g}".format(float(it.quantity or 1)))}</td>'
            f'<td class="center">{esc(it.unit)}</td>'
            f'<td class="num">{money(it.price)}</td>'
            f'<td class="num">{money(it.amount)}</td>'
            "</tr>"
        )

    if inv.vat_rate and float(inv.vat_rate) > 0:
        vat_html = f'<tr><td>НДС {("{:g}".format(float(inv.vat_rate)))}%:</td><td class="num">{money(inv.vat_amount)}</td></tr>'
    else:
        vat_html = '<tr><td>НДС:</td><td class="num">Без НДС</td></tr>'

    paid_html = ""
    if (inv.paid_amount or 0) > 0:
        paid_html = (
            f'<tr><td>Оплачено:</td><td class="num">{money(inv.paid_amount)}</td></tr>'
            f'<tr><td>Остаток:</td><td class="num">{money(max(0.0, (inv.total or 0) - (inv.paid_amount or 0)))}</td></tr>'
        )

    notes_html = f'<div class="notes"><b>Примечание:</b> {esc(inv.notes)}</div>' if inv.notes else ""
    status_text = compute_status(inv)
    director = comp.get("director") or ""
    accountant = comp.get("accountant") or ""

    css = """
* { box-sizing: border-box; }
body { font-family: Arial, "Segoe UI", sans-serif; color: #000; margin: 0; background: #fff; }
.print-btn { position: fixed; top: 16px; right: 16px; padding: 10px 18px; background: #111; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; z-index: 99; }
@media print { .no-print { display: none !important; } @page { size: A4; margin: 15mm; } }
.doc { max-width: 210mm; margin: 0 auto; padding: 24px; }
.header { display: flex; gap: 20px; align-items: flex-start; border-bottom: 3px solid #000; padding-bottom: 16px; margin-bottom: 18px; }
.logo { max-height: 70px; max-width: 180px; object-fit: contain; }
.company-name { font-size: 20px; font-weight: 700; margin-bottom: 6px; }
.company div { font-size: 12px; margin: 2px 0; }
.title { font-size: 20px; text-align: center; margin: 18px 0; text-transform: uppercase; letter-spacing: 1px; }
.status { text-align: center; margin-bottom: 12px; font-size: 12px; color: #444; }
.meta { display: grid; grid-template-columns: 1fr 1fr; gap: 6px 24px; margin-bottom: 18px; font-size: 13px; }
.meta .label { color: #444; }
.items { width: 100%; border-collapse: collapse; margin-bottom: 16px; font-size: 12px; }
.items th { border: 1px solid #000; padding: 6px; background: #f2f2f2; text-align: left; }
.items td { border: 1px solid #000; padding: 6px; vertical-align: top; }
.items .num { text-align: right; white-space: nowrap; }
.items .center { text-align: center; }
.desc { color: #444; font-size: 11px; margin-top: 3px; }
.totals { display: flex; justify-content: flex-end; margin-bottom: 16px; }
.totals-table { border-collapse: collapse; min-width: 320px; font-size: 13px; }
.totals-table td { padding: 5px 10px; }
.totals-table .num { text-align: right; font-weight: 600; white-space: nowrap; }
.totals-table .grand td { font-size: 16px; font-weight: 800; border-top: 2px solid #000; }
.purpose { font-size: 12px; margin: 16px 0; padding: 10px; border: 1px dashed #999; }
.notes { font-size: 12px; margin: 10px 0; color: #333; }
.signs { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 50px; font-size: 12px; }
.sign .line { border-bottom: 1px solid #000; height: 24px; margin-bottom: 4px; }
"""

    bank_line = ""
    if comp.get("bank") or comp.get("account"):
        bank_line = f'<div>Банк: {esc(comp.get("bank"))}, БИК {esc(comp.get("bik"))}, р/с {esc(comp.get("account"))}</div>'

    email_part = f' · {esc(comp.get("email"))}' if comp.get("email") else ""

    body = (
        '<button class="no-print print-btn" onclick="window.print()">🖨 Печать / Сохранить PDF</button>'
        '<div class="doc">'
        '<div class="header">' + logo_html + '<div class="company">'
        f'<div class="company-name">{esc(comp.get("name"))}</div>'
        f'<div>ИНН {esc(comp.get("inn"))} / КПП {esc(comp.get("kpp") or "—")}</div>'
        f'<div>{esc(comp.get("address"))}</div>'
        f'<div>Тел.: {esc(comp.get("phone"))}{email_part}</div>'
        + bank_line +
        '</div></div>'
        f'<h1 class="title">Счёт на оплату № {esc(inv.number)} от {fmt_date(inv.date)}</h1>'
        f'<div class="status">Статус: {esc(status_text)}' + (f' · Срок оплаты: {fmt_date(inv.due_date)}' if inv.due_date else "") + '</div>'
        '<div class="meta">'
        f'<div><span class="label">Плательщик:</span> <b>{esc(obj.name if obj else "")}</b></div>'
        f'<div><span class="label">ИНН плательщика:</span> {esc(getattr(obj, "inn", "") if obj else "—")}</div>'
        f'<div><span class="label">Адрес:</span> {esc(obj.address if obj else "")}</div>'
        f'<div><span class="label">Срок оплаты:</span> {fmt_date(inv.due_date)}</div>'
        '</div>'
        '<table class="items"><thead><tr><th style="width:30px">№</th><th>Наименование</th><th style="width:60px">Кол-во</th><th style="width:60px">Ед.</th><th style="width:110px">Цена</th><th style="width:120px">Сумма</th></tr></thead>'
        f'<tbody>{rows_html}</tbody></table>'
        '<div class="totals"><table class="totals-table">'
        f'<tr><td>Итого без НДС:</td><td class="num">{money(inv.subtotal)}</td></tr>'
        f'{vat_html}'
        f'<tr class="grand"><td>ВСЕГО К ОПЛАТЕ:</td><td class="num">{money(inv.total)}</td></tr>'
        f'{paid_html}'
        '</table></div>'
        f'<div class="purpose"><b>Назначение платежа:</b> {esc(inv.payment_purpose or ("Оплата по счёту " + inv.number + " от " + fmt_date(inv.date)))}</div>'
        f'{notes_html}'
        '<div class="signs">'
        f'<div class="sign"><div class="line"></div>Руководитель' + (f' / {esc(director)}' if director else "") + '</div>'
        f'<div class="sign"><div class="line"></div>Бухгалтер' + (f' / {esc(accountant)}' if accountant else "") + '</div>'
        '</div>'
        '</div>'
    )

    return HTMLResponse('<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Счёт ' + esc(inv.number) + '</title><style>' + css + '</style></head><body>' + body + '</body></html>')


@router.get("/{iid}/act", response_class=HTMLResponse)
def print_act(iid: str, db: Session = Depends(get_db)):
    inv = db.query(Invoice).filter(Invoice.id == iid).first()
    if not inv:
        raise HTTPException(404, "Счёт не найден")

    obj = db.query(Object).filter(Object.id == inv.object_id).first()
    items = db.query(InvoiceItem).filter(InvoiceItem.invoice_id == inv.id).order_by(InvoiceItem.id).all()
    comp = get_company(db, getattr(inv, "company_id", None))

    logo_html = ""
    if (STATIC_DIR / "logo.png").exists():
        logo_html = '<img src="/static/logo.png" class="logo" alt="logo">'

    rows_html = ""
    for idx, it in enumerate(items, 1):
        desc_html = f'<div class="desc">{esc(it.description)}</div>' if it.description else ""
        rows_html += (
            "<tr>"
            f'<td class="center">{idx}</td>'
            f"<td>{esc(it.name)}{desc_html}</td>"
            f'<td class="num">{("{:g}".format(float(it.quantity or 1)))}</td>'
            f'<td class="center">{esc(it.unit)}</td>'
            f'<td class="num">{money(it.price)}</td>'
            f'<td class="num">{money(it.amount)}</td>'
            "</tr>"
        )

    if inv.vat_rate and float(inv.vat_rate) > 0:
        vat_html = f'<tr><td>В том числе НДС {("{:g}".format(float(inv.vat_rate)))}%:</td><td class="num">{money(inv.vat_amount)}</td></tr>'
    else:
        vat_html = '<tr><td>НДС:</td><td class="num">Без НДС</td></tr>'

    director = comp.get("director") or ""
    client_contact = getattr(obj, "contact_person", "") or ""

    css = """
* { box-sizing: border-box; }
body { font-family: Arial, "Segoe UI", sans-serif; color: #000; margin: 0; background: #fff; }
.print-btn { position: fixed; top: 16px; right: 16px; padding: 10px 18px; background: #111; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; z-index: 99; }
@media print { .no-print { display: none !important; } @page { size: A4; margin: 15mm; } }
.doc { max-width: 210mm; margin: 0 auto; padding: 24px; }
.header { display: flex; gap: 20px; align-items: flex-start; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px; }
.logo { max-height: 60px; max-width: 160px; object-fit: contain; }
.company-name { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.company div { font-size: 12px; margin: 2px 0; }
.title { font-size: 18px; text-align: center; margin: 16px 0 6px 0; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; }
.subtitle { text-align: center; margin-bottom: 16px; font-size: 12px; color: #444; }
.parties { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; font-size: 12.5px; }
.party-row { display: grid; grid-template-columns: 110px 1fr; gap: 8px; }
.party-label { font-weight: 700; color: #222; }
.items { width: 100%; border-collapse: collapse; margin-bottom: 14px; font-size: 12px; }
.items th { border: 1px solid #000; padding: 6px; background: #f2f2f2; text-align: left; }
.items td { border: 1px solid #000; padding: 6px; vertical-align: top; }
.items .num { text-align: right; white-space: nowrap; }
.items .center { text-align: center; }
.desc { color: #555; font-size: 11px; margin-top: 2px; }
.totals { display: flex; justify-content: flex-end; margin-bottom: 14px; }
.totals-table { border-collapse: collapse; min-width: 320px; font-size: 12.5px; }
.totals-table td { padding: 4px 8px; }
.totals-table .num { text-align: right; font-weight: 600; white-space: nowrap; }
.totals-table .grand td { font-size: 15px; font-weight: 800; border-top: 2px solid #000; }
.result-text { font-size: 12px; margin: 14px 0; line-height: 1.5; padding: 8px; background: #fafafa; border: 1px solid #e0e0e0; }
.signs { display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 40px; font-size: 12px; }
.sign .title-role { font-weight: 700; margin-bottom: 10px; }
.sign .line { border-bottom: 1px solid #000; height: 26px; margin-bottom: 4px; }
.sign .hint { font-size: 10px; color: #666; text-align: center; }
"""

    bank_line = ""
    if comp.get("bank") or comp.get("account"):
        bank_line = f', р/с {esc(comp.get("account"))} в {esc(comp.get("bank"))}, БИК {esc(comp.get("bik"))}'

    executor_info = f'{esc(comp.get("name"))}, ИНН {esc(comp.get("inn"))}, КПП {esc(comp.get("kpp") or "—")}, адрес: {esc(comp.get("address"))}{bank_line}'
    customer_info = f'{esc(obj.name if obj else "")}, ИНН {esc(getattr(obj, "inn", "") if obj else "—")}, адрес: {esc(obj.address if obj else "")}'

    body = (
        '<button class="no-print print-btn" onclick="window.print()">🖨 Печать / Сохранить PDF</button>'
        '<div class="doc">'
        '<div class="header">' + logo_html + '<div class="company">'
        f'<div class="company-name">{esc(comp.get("name"))}</div>'
        f'<div>ИНН {esc(comp.get("inn"))} / КПП {esc(comp.get("kpp") or "—")} · {esc(comp.get("address"))}</div>'
        '</div></div>'
        f'<h1 class="title">Акт сдачи-приемки выполненных работ (услуг)</h1>'
        f'<div class="subtitle">к Счёту № {esc(inv.number)} от {fmt_date(inv.date)}</div>'
        '<div class="parties">'
        f'<div class="party-row"><div class="party-label">Исполнитель:</div><div>{executor_info}</div></div>'
        f'<div class="party-row"><div class="party-label">Заказчик:</div><div>{customer_info}</div></div>'
        '</div>'
        '<table class="items"><thead><tr><th style="width:30px">№</th><th>Наименование работ, услуг</th><th style="width:60px">Кол-во</th><th style="width:50px">Ед.</th><th style="width:110px">Цена</th><th style="width:120px">Сумма</th></tr></thead>'
        f'<tbody>{rows_html}</tbody></table>'
        '<div class="totals"><table class="totals-table">'
        f'<tr><td>Итого без НДС:</td><td class="num">{money(inv.subtotal)}</td></tr>'
        f'{vat_html}'
        f'<tr class="grand"><td>ВСЕГО:</td><td class="num">{money(inv.total)}</td></tr>'
        '</table></div>'
        f'<div class="result-text">'
        f'Всего оказано услуг / выполнено работ {len(items)}, на сумму <b>{money(inv.total)}</b>.<br>'
        'Вышеперечисленные работы (услуги) выполнены полностью и в срок. Заказчик претензий по объему, качеству и срокам оказания услуг претензий не имеет.'
        '</div>'
        '<div class="signs">'
        '<div class="sign">'
        '<div class="title-role">Исполнитель:</div>'
        '<div class="line"></div>'
        f'<div class="hint">(подпись) / {esc(director or "Руководитель")}</div>'
        '<div style="margin-top:20px;font-size:11px;color:#888;">М.П.</div>'
        '</div>'
        '<div class="sign">'
        '<div class="title-role">Заказчик:</div>'
        '<div class="line"></div>'
        f'<div class="hint">(подпись) / {esc(client_contact or "Представитель заказчика")}</div>'
        '<div style="margin-top:20px;font-size:11px;color:#888;">М.П.</div>'
        '</div>'
        '</div>'
        '</div>'
    )

    return HTMLResponse('<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Акт к счёту ' + esc(inv.number) + '</title><style>' + css + '</style></head><body>' + body + '</body></html>')

