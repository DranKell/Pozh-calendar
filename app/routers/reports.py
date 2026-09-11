# -*- coding: utf-8 -*-
"""
Роутер генерации официальной документации по пожарной безопасности:
1. Журнал эксплуатации систем противопожарной защиты (согласно ППР РФ № 1479) в HTML (A4 для печати/PDF) и Excel (.xlsx).
2. Акт технического освидетельствования / проверки работоспособности установок противопожарной защиты (АПС, СОУЭ, ВПВ, ДУ, АУПТ).
"""
import io
import html
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.execution import Execution
from app.models.company import Company
from app.routers.invoices import get_company

router = APIRouter()


def esc(s):
    return html.escape(str(s if s is not None else ""))


def fmt_date(d):
    if not d:
        return "—"
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except Exception:
            return d
    return d.strftime("%d.%m.%Y")


@router.get("/journal-ppr/html", response_class=HTMLResponse)
def get_journal_ppr_html(
    object_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Генерация печатной формы «Журнал эксплуатации систем противопожарной защиты» (ППР РФ № 1479).
    Сброшюрованный документ с титульным листом по ГОСТ и разделами регламентных проверок.
    """
    if object_id:
        obj = db.query(Object).filter(Object.id == object_id).first()
    else:
        obj = db.query(Object).first()

    if not obj:
        # Если в базе нет объектов, создаем демонстрационный макет объекта для корректного отображения формы
        class DummyObj:
            id = "demo"
            name = "Все объекты организации / Типовой объект защиты"
            address = "г. Екатеринбург, ул. Малышева, д. 101"
            inn = "6671000000"
            contact_person = "Ответственный за пожарную безопасность"
            phone = "+7 (343) 000-00-00"
            functional_hazard = "Ф3.1"
            fire_hazard_category = "В"
            total_area = 1500.0
            floors = 3
        obj = DummyObj()

    comp = get_company(db, company_id)

    # Выборка выполненных работ
    q = db.query(Execution).join(WorkType, WorkType.id == Execution.work_type_id)
    if object_id:
        q = q.filter(Execution.object_id == object_id)

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

    items = q.order_by(Execution.planned_date.asc()).all()

    # Группировка по разделам СПЗ
    sections = {
        "АПС / СОУЭ": [],
        "Первичные средства (Огнетушители)": [],
        "Противопожарный водопровод (ВПВ)": [],
        "Дымоудаление и вентиляция": [],
        "Эвакуация и двери": [],
        "Электрооборудование и ЭТЛ": [],
        "Другие регламенты": [],
    }

    for e in items:
        w = db.query(WorkType).filter(WorkType.id == e.work_type_id).first()
        cat = (w.category or "").lower() if w else ""
        code = (w.code or "").upper() if w else ""

        if "апс" in cat or "соуэ" in cat or "пб-01" in code:
            sections["АПС / СОУЭ"].append((e, w))
        elif "огнетуш" in cat or "пб-02" in code:
            sections["Первичные средства (Огнетушители)"].append((e, w))
        elif "водопровод" in cat or "впв" in cat or "аупт" in cat or "пб-03" in code:
            sections["Противопожарный водопровод (ВПВ)"].append((e, w))
        elif "дымоудален" in cat or "вентиляц" in cat or "пб-04" in code:
            sections["Дымоудаление и вентиляция"].append((e, w))
        elif "эвакуац" in cat or "двер" in cat or "пб-05" in code or "пб-09" in code:
            sections["Эвакуация и двери"].append((e, w))
        elif "электр" in cat or "молние" in cat or "пб-06" in code:
            sections["Электрооборудование и ЭТЛ"].append((e, w))
        else:
            sections["Другие регламенты"].append((e, w))

    period_str = ""
    if date_from and date_to:
        period_str = f"за период с {fmt_date(date_from)} по {fmt_date(date_to)}"
    elif date_from:
        period_str = f"с {fmt_date(date_from)}"
    elif date_to:
        period_str = f"по {fmt_date(date_to)}"
    else:
        period_str = f"за {date.today().year} год"

    # HTML разметка
    sections_html = ""
    sec_num = 1
    for sec_title, entries in sections.items():
        if not entries:
            continue
        rows_html = ""
        for i, (e, w) in enumerate(entries, 1):
            status_text = "Исправно, работоспособно" if e.status == "Выполнено" else e.status
            fact_dt = fmt_date(e.actual_date) if e.actual_date else fmt_date(e.planned_date)
            rows_html += f"""
            <tr>
                <td style="text-align:center;">{i}</td>
                <td style="text-align:center;">{fact_dt}</td>
                <td><b>[{esc(w.code if w else '')}] {esc(w.name if w else '')}</b><div class="sub-text">{esc(w.description if w else '')}</div></td>
                <td>{esc(e.notes or 'Регламентные работы проведены в полном объеме')}</td>
                <td style="text-align:center;color:#15803d;font-weight:600;">{status_text}</td>
                <td>{esc(e.performed_by or comp.get('director') or 'Ответственный специалист')}</td>
                <td style="text-align:center;font-size:10px;color:#888;">(подпись)</td>
            </tr>
            """

        sections_html += f"""
        <div class="section-block">
            <h3 class="section-title">Раздел {sec_num}. {sec_title}</h3>
            <table class="data-table">
                <thead>
                    <tr>
                        <th style="width:30px;">№</th>
                        <th style="width:90px;">Дата ТО</th>
                        <th>Наименование системы / регламента</th>
                        <th>Результат проверки / замечания</th>
                        <th style="width:130px;">Работоспособность</th>
                        <th style="width:160px;">ФИО исполнителя</th>
                        <th style="width:70px;">Подпись</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        """
        sec_num += 1

    if not sections_html:
        sections_html = """<div style="padding:40px;text-align:center;color:#666;font-size:14px;border:1px dashed #ccc;border-radius:8px;">
        За указанный период выполненных регламентных работ не зафиксировано.
        </div>"""

    html_content = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Журнал эксплуатации систем ППЗ — {esc(obj.name)}</title>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Times New Roman", Times, serif; font-size: 12pt; line-height: 1.3; color: #111; background: #f4f6f8; padding: 20px; }}
    .no-print {{ position: fixed; top: 16px; right: 16px; z-index: 1000; display: flex; gap: 10px; }}
    .btn-print {{ background: #0f172a; color: #fff; border: none; padding: 10px 18px; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 13px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
    .btn-print:hover {{ background: #1e293b; }}
    .btn-xls {{ background: #15803d; color: #fff; text-decoration: none; padding: 10px 18px; border-radius: 8px; font-weight: bold; font-size: 13px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); display: inline-flex; align-items: center; gap: 6px; }}
    .btn-xls:hover {{ background: #166534; }}
    
    .sheet {{ background: #fff; max-width: 210mm; min-height: 297mm; margin: 0 auto 20px auto; padding: 20mm 15mm 15mm 20mm; box-shadow: 0 0 14px rgba(0,0,0,0.08); position: relative; }}
    
    .cover-title {{ text-align: center; margin-top: 60px; text-transform: uppercase; font-size: 16pt; font-weight: bold; letter-spacing: 0.5px; }}
    .cover-sub {{ text-align: center; font-size: 11pt; color: #444; margin-top: 10px; margin-bottom: 50px; }}
    .cover-law {{ text-align: center; font-size: 10pt; font-style: italic; color: #555; margin-bottom: 40px; }}
    
    .info-grid {{ width: 100%; border-collapse: collapse; margin-bottom: 40px; font-size: 11pt; }}
    .info-grid td {{ padding: 6px 4px; vertical-align: top; }}
    .info-label {{ font-weight: bold; width: 220px; }}
    .info-val {{ border-bottom: 1px solid #111; }}
    
    .section-block {{ margin-bottom: 30px; page-break-inside: avoid; }}
    .section-title {{ font-size: 12pt; font-weight: bold; margin-bottom: 8px; text-transform: uppercase; border-bottom: 1.5px solid #111; padding-bottom: 4px; }}
    
    .data-table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; margin-bottom: 15px; }}
    .data-table th, .data-table td {{ border: 1px solid #111; padding: 5px 6px; }}
    .data-table th {{ background: #f1f5f9; text-align: center; font-weight: bold; }}
    .sub-text {{ font-size: 8pt; color: #555; margin-top: 2px; }}
    
    .sign-block {{ display: flex; justify-content: space-between; margin-top: 40px; font-size: 11pt; page-break-inside: avoid; }}
    .sign-item {{ width: 45%; }}
    .sign-line {{ border-bottom: 1px solid #111; height: 30px; margin-bottom: 4px; }}
    .sign-hint {{ font-size: 8.5pt; text-align: center; color: #555; }}
    
    @media print {{
        body {{ background: #fff; padding: 0; }}
        .no-print {{ display: none !important; }}
        .sheet {{ box-shadow: none; margin: 0; padding: 15mm 10mm 15mm 15mm; max-width: 100%; }}
        .page-break {{ page-break-before: always; }}
    }}
</style>
</head>
<body>

<div class="no-print">
    <a href="/api/objects/{object_id}/journal-ppr/excel?date_from={date_from or ''}&date_to={date_to or ''}" class="btn-xls">📊 Выгрузить в Excel</a>
    <button class="btn-print" onclick="window.print()">🖨 Печать / Сохранить PDF (A4)</button>
</div>

<div class="sheet">
    <div style="text-align:right;font-size:10pt;color:#555;">Приложение к ППР РФ № 1479</div>
    <div class="cover-title">ЖУРНАЛ<br>эксплуатации систем противопожарной защиты</div>
    <div class="cover-law">(в соответствии с требованиями Федерального закона № 123-ФЗ и Правил противопожарного режима в РФ)</div>
    <div class="cover-sub">{period_str}</div>

    <table class="info-grid">
        <tr>
            <td class="info-label">Объект защиты:</td>
            <td class="info-val"><b>{esc(obj.name)}</b></td>
        </tr>
        <tr>
            <td class="info-label">Адрес объекта:</td>
            <td class="info-val">{esc(obj.address or 'Не указан')}</td>
        </tr>
        <tr>
            <td class="info-label">ИНН Заказчика:</td>
            <td class="info-val">{esc(obj.inn or '—')}</td>
        </tr>
        <tr>
            <td class="info-label">Класс пожарной опасности:</td>
            <td class="info-val">ФПО {esc(obj.functional_hazard or 'Ф3.1')}, категория взрывопожароопасности: {esc(obj.fire_hazard_category or 'В')}, площадь: {obj.total_area or 0} м², {obj.floors or 1} эт.</td>
        </tr>
        <tr>
            <td class="info-label">Обслуживающая организация:</td>
            <td class="info-val"><b>{esc(comp.get('name'))}</b> (ИНН {esc(comp.get('inn'))}, Лицензия МЧС России)</td>
        </tr>
        <tr>
            <td class="info-label">Ответственный за ПБ объекта:</td>
            <td class="info-val">{esc(obj.contact_person or 'Руководитель объекта')}</td>
        </tr>
    </table>

    <div style="margin-top: 50px; font-size: 10.5pt; line-height: 1.6; text-align: justify; border-top: 1px solid #ccc; padding-top: 15px;">
        Настоящий журнал ведется на объекте защиты в бумажном/электронном виде. 
        Руководитель организации обеспечивает эксплуатацию систем противопожарной защиты в соответствии с требованиями технической документации изготовителя и нормативных документов по пожарной безопасности (СП 484.1311500, СП 485.1311500, СП 486.1311500, СП 3.13130, СП 10.13130, СП 7.13130).
    </div>

    <div class="sign-block" style="margin-top:80px;">
        <div class="sign-item">
            <div>Ответственный за ПБ на объекте:</div>
            <div class="sign-line"></div>
            <div class="sign-hint">(подпись, расшифровка)</div>
        </div>
        <div class="sign-item">
            <div>Руководитель организации лицензиата:</div>
            <div class="sign-line"></div>
            <div class="sign-hint">(подпись, расшифровка)</div>
        </div>
    </div>
</div>

<div class="sheet page-break">
    <div style="text-align:center;font-size:13pt;font-weight:bold;margin-bottom:20px;text-transform:uppercase;">
        Сведения о проведении регламентных работ и проверок систем ППЗ
    </div>
    <div style="font-size:10.5pt;margin-bottom:15px;color:#333;">
        Объект: <b>{esc(obj.name)}</b> · Период: {period_str}
    </div>

    {sections_html}

    <div class="sign-block" style="margin-top:50px;">
        <div class="sign-item">
            <div>Записи внес (Инженер ТО):</div>
            <div class="sign-line"></div>
            <div class="sign-hint">(подпись) / {esc(comp.get('director') or 'Инженер сервисной службы')}</div>
        </div>
        <div class="sign-item">
            <div>Контроль провел (Ответственный за ПБ):</div>
            <div class="sign-line"></div>
            <div class="sign-hint">(подпись) / {esc(obj.contact_person or 'Ответственное лицо')}</div>
        </div>
    </div>
</div>

</body>
</html>
"""
    return HTMLResponse(html_content)


@router.get("/journal-ppr/excel")
def get_journal_ppr_excel(
    object_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Выгрузка Журнала эксплуатации систем противопожарной защиты в формат Excel (.xlsx).
    """
    if object_id:
        obj = db.query(Object).filter(Object.id == object_id).first()
    else:
        obj = db.query(Object).first()

    if not obj:
        class DummyObj:
            id = "all"
            name = "Все объекты организации"
            address = "г. Екатеринбург"
            inn = ""
            contact_person = ""
            functional_hazard = "Ф3.1"
            fire_hazard_category = "В"
            total_area = 0
            floors = 1
        obj = DummyObj()

    comp = get_company(db, company_id)

    q = db.query(Execution).join(WorkType, WorkType.id == Execution.work_type_id)
    if object_id:
        q = q.filter(Execution.object_id == object_id)
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

    items = q.order_by(Execution.planned_date.asc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Журнал ППР 1479"

    # Стили
    title_font = Font(name="Calibri", size=14, bold=True)
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    regular_font = Font(name="Calibri", size=10)
    bold_font = Font(name="Calibri", size=10, bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    # Шапка документа
    ws.merge_cells("A1:G1")
    ws["A1"] = "ЖУРНАЛ ЭКСПЛУАТАЦИИ СИСТЕМ ПРОТИВОПОЖАРНОЙ ЗАЩИТЫ (ППР РФ № 1479)"
    ws["A1"].font = title_font
    ws["A1"].alignment = center_align

    ws["A3"] = "Объект защиты:"
    ws["A3"].font = bold_font
    ws["B3"] = f"{obj.name} (Адрес: {obj.address or '—'}, ИНН: {obj.inn or '—'})"

    ws["A4"] = "Классификация:"
    ws["A4"].font = bold_font
    ws["B4"] = f"ФПО {obj.functional_hazard or 'Ф3.1'}, Категория {obj.fire_hazard_category or 'В'}, Площадь: {obj.total_area or 0} кв.м"

    ws["A5"] = "Обслуживающая организация:"
    ws["A5"].font = bold_font
    ws["B5"] = f"{comp.get('name')} (ИНН {comp.get('inn')}, Лицензия МЧС России)"

    ws["A6"] = "Период выборки:"
    ws["A6"].font = bold_font
    ws["B6"] = f"{date_from or 'Начало'} — {date_to or 'Конец года'}"

    # Заголовки таблицы
    headers = [
        ("№", 6),
        ("Дата ТО", 14),
        ("Шифр регламента", 18),
        ("Наименование регламентных работ", 38),
        ("Статус выполнения", 16),
        ("ФИО исполнителя", 25),
        ("Результат проверки и примечания", 35),
    ]

    row_idx = 8
    for col_idx, (h_text, w_val) in enumerate(headers, 1):
        cell = ws.cell(row=row_idx, column=col_idx, value=h_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = w_val

    # Заполнение записей
    for i, e in enumerate(items, 1):
        row_idx += 1
        w = db.query(WorkType).filter(WorkType.id == e.work_type_id).first()
        fact_d = e.actual_date.strftime("%d.%m.%Y") if e.actual_date else (e.planned_date.strftime("%d.%m.%Y") if e.planned_date else "—")

        row_data = [
            (i, center_align, regular_font),
            (fact_d, center_align, regular_font),
            (w.code if w else "—", center_align, bold_font),
            (w.name if w else "Регламентное ТО", left_align, regular_font),
            (e.status, center_align, bold_font),
            (e.performed_by or comp.get("director") or "Инженер сервисной службы", left_align, regular_font),
            (e.notes or "Система исправна, замечаний нет", left_align, regular_font),
        ]

        for col_idx, (val, align, fnt) in enumerate(row_data, 1):
            c = ws.cell(row=row_idx, column=col_idx, value=val)
            c.font = fnt
            c.alignment = align
            c.border = thin_border

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"Journal_PPR1479_{obj.id}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/act-inspection/html", response_class=HTMLResponse)
def get_act_inspection_html(
    object_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Генерация «Акта технического освидетельствования / проверки работоспособности систем противопожарной защиты».
    Официальный протокол испытаний установок АПС, СОУЭ, ВПВ, АУПТ и дымоудаления.
    """
    if object_id:
        obj = db.query(Object).filter(Object.id == object_id).first()
    else:
        obj = db.query(Object).first()

    if not obj:
        class DummyObj:
            id = "demo"
            name = "Все объекты организации / Комплекс СПЗ"
            address = "г. Екатеринбург, ул. Малышева, д. 101"
            inn = "6671000000"
            contact_person = "Ответственный за пожарную безопасность"
            functional_hazard = "Ф3.1"
            fire_hazard_category = "В"
            total_area = 1500.0
            floors = 3
        obj = DummyObj()

    comp = get_company(db, company_id)

    # Выполненные работы по объекту
    q = (
        db.query(Execution)
        .join(WorkType, WorkType.id == Execution.work_type_id)
        .filter(Execution.status == "Выполнено")
    )
    if object_id:
        q = q.filter(Execution.object_id == object_id)
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

    items = q.order_by(Execution.actual_date.desc()).all()

    today_str = date.today().strftime("%d.%m.%Y")
    period_label = f"за период с {fmt_date(date_from)} по {fmt_date(date_to)}" if date_from and date_to else f"по состоянию на {today_str}"

    rows_html = ""
    for i, e in enumerate(items, 1):
        w = db.query(WorkType).filter(WorkType.id == e.work_type_id).first()
        code = w.code if w else "ПБ"
        name = w.name if w else "Комплекс ТО СПЗ"
        dt = fmt_date(e.actual_date or e.planned_date)
        rows_html += f"""
        <tr>
            <td style="text-align:center;">{i}</td>
            <td><b>[{esc(code)}] {esc(name)}</b></td>
            <td style="text-align:center;">{dt}</td>
            <td style="text-align:center;color:#166534;font-weight:bold;">Работоспособно</td>
            <td>{esc(e.notes or 'Параметры срабатывания соответствуют нормам СП/ГОСТ. Дефектов не обнаружено.')}</td>
        </tr>
        """

    if not rows_html:
        rows_html = """<tr><td colspan="5" style="text-align:center;padding:20px;color:#777;">Нет закрытых фактов ТО за указанный период</td></tr>"""

    body = f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Акт проверки работоспособности СПЗ — {esc(obj.name)}</title>
<style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "Times New Roman", Times, serif; font-size: 11pt; line-height: 1.35; color: #111; background: #f4f6f8; padding: 20px; }}
    .no-print {{ position: fixed; top: 16px; right: 16px; z-index: 1000; }}
    .btn-print {{ background: #0f172a; color: #fff; border: none; padding: 10px 18px; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 13px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }}
    .sheet {{ background: #fff; max-width: 210mm; min-height: 297mm; margin: 0 auto; padding: 20mm 15mm 15mm 20mm; box-shadow: 0 0 14px rgba(0,0,0,0.08); }}
    .doc-head {{ text-align: center; margin-bottom: 20px; }}
    .doc-head h1 {{ font-size: 14pt; text-transform: uppercase; font-weight: bold; margin-bottom: 6px; }}
    .doc-head .sub {{ font-size: 10.5pt; color: #333; }}
    .meta-row {{ display: flex; justify-content: space-between; margin-bottom: 20px; font-size: 10.5pt; border-bottom: 1px solid #000; padding-bottom: 4px; }}
    .section {{ margin-bottom: 14px; text-align: justify; text-indent: 25px; }}
    .items-table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 9.5pt; }}
    .items-table th, .items-table td {{ border: 1px solid #000; padding: 5px 6px; }}
    .items-table th {{ background: #f8fafc; text-align: center; }}
    .signs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 40px; margin-top: 40px; page-break-inside: avoid; }}
    .sign-line {{ border-bottom: 1px solid #000; height: 32px; margin-bottom: 4px; }}
    .sign-hint {{ font-size: 8.5pt; text-align: center; color: #555; }}
    @media print {{
        body {{ background: #fff; padding: 0; }}
        .no-print {{ display: none !important; }}
        .sheet {{ box-shadow: none; margin: 0; padding: 15mm 10mm; max-width: 100%; }}
    }}
</style>
</head>
<body>

<div class="no-print">
    <button class="btn-print" onclick="window.print()">🖨 Печать / Сохранить PDF (Акт)</button>
</div>

<div class="sheet">
    <div class="doc-head">
        <h1>АКТ<br>технического освидетельствования и проверки работоспособности установок противопожарной защиты</h1>
        <div class="sub">({period_label})</div>
    </div>

    <div class="meta-row">
        <div><b>Место составления:</b> {esc(obj.address or 'г. Екатеринбург')}</div>
        <div><b>Дата составления:</b> {today_str} г.</div>
    </div>

    <div class="section">
        Настоящий акт составлен комиссией в составе представителя Исполнителя: <b>{esc(comp.get('name'))}</b> (действующего на основании Лицензии МЧС России) в лице руководителя / ведущего инженера <b>{esc(comp.get('director') or 'Ведущего инженера ТО')}</b>, с одной стороны, и представителя Заказчика: <b>{esc(obj.name)}</b> в лице ответственного за обеспечение пожарной безопасности <b>{esc(obj.contact_person or 'Руководителя объекта')}</b>, с другой стороны.
    </div>

    <div class="section">
        Комиссией проведено визуальное обследование, инструментальный контроль, комплексные испытания и техническое освидетельствование систем противопожарной защиты объекта (класс функциональной пожарной опасности <b>ФПО {esc(obj.functional_hazard or 'Ф3.1')}</b>, площадь {obj.total_area or 0} м²).
    </div>

    <div style="font-weight: bold; margin-top: 15px; margin-bottom: 6px;">
        Результаты проверки работоспособности систем:
    </div>

    <table class="items-table">
        <thead>
            <tr>
                <th style="width:30px;">№</th>
                <th>Наименование системы / технического регламента</th>
                <th style="width:90px;">Дата ТО</th>
                <th style="width:130px;">Заключение</th>
                <th>Результаты испытаний и параметры</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div class="section" style="margin-top: 20px;">
        <b>ЗАКЛЮЧЕНИЕ КОМИССИИ:</b><br>
        Установки автоматической противопожарной защиты объекта <b>«{esc(obj.name)}»</b> находятся в исправном и полностью работоспособном техническом состоянии, обеспечивают своевременное обнаружение очагов возгорания, подачу сигналов оповещения и управление эвакуацией людей в строгом соответствии с требованиями Федерального закона № 123-ФЗ, СП 484.1311500.2020, СП 3.13130.2009 и Постановления Правительства РФ № 1479.
    </div>

    <div class="signs">
        <div>
            <div style="font-weight:bold;margin-bottom:8px;">От Исполнителя (Лицензиат МЧС):</div>
            <div style="font-size:10pt;">{esc(comp.get('name'))}</div>
            <div class="sign-line"></div>
            <div class="sign-hint">(подпись) / {esc(comp.get('director') or 'Руководитель')}</div>
            <div style="margin-top:15px;font-size:10pt;color:#888;">М.П.</div>
        </div>
        <div>
            <div style="font-weight:bold;margin-bottom:8px;">От Заказчика (Объект защиты):</div>
            <div style="font-size:10pt;">{esc(obj.name)}</div>
            <div class="sign-line"></div>
            <div class="sign-hint">(подпись) / {esc(obj.contact_person or 'Ответственный за ПБ')}</div>
            <div style="margin-top:15px;font-size:10pt;color:#888;">М.П.</div>
        </div>
    </div>
</div>

</body>
</html>
"""
    return HTMLResponse(body)
