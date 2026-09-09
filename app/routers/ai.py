# -*- coding: utf-8 -*-
"""
Роутер ИИ-помощника: анализ объектов, подбор работ по 123-ФЗ, умные пресеты и пакетное назначение работ.
"""
from datetime import date
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.execution import Execution
from app.models.company import Company
from app.services.ai_service import (
    load_ai_config,
    get_expert_rules_recommendations,
    call_llm_advisor,
    get_preset_for_building_type,
    verify_llm_connection,
    get_provider_display_name,
    answer_assistant_question,
    ai_parse_organizations,
)
from app.services.doc_parser import extract_text_from_file
from app.services.periodicity import generate_schedule

router = APIRouter()



class AnalyzeObjectRequest(BaseModel):
    objectId: Optional[str] = None
    category: Optional[str] = None
    functionalHazard: Optional[str] = "Ф3.1"
    fireHazardCategory: Optional[str] = "В"
    totalArea: Optional[float] = 0.0
    floors: Optional[int] = 1


class AskQuestionRequest(BaseModel):
    question: str
    contextPage: Optional[str] = "dashboard"


class QuickPresetRequest(BaseModel):
    query: str


class ApplyRecommendationsRequest(BaseModel):
    objectId: str
    workCodes: List[str]
    startDate: Optional[str] = None
    endDate: Optional[str] = None



@router.get("/config")
def get_status_config(check: bool = True):
    """
    Проверка конфигурации и реального статуса ИИ (из msg.cfg).
    Если check=True (по умолчанию), выполняет проверку подключения к API.
    """
    cfg = load_ai_config()
    enabled = cfg.get("enabled", True)
    has_key = bool(cfg.get("api_key"))
    provider = cfg.get("provider", "yandexgpt")
    model = cfg.get("model", "yandexgpt/latest")
    display_provider = get_provider_display_name(provider, model)

    health = verify_llm_connection(cfg, force_check=False)

    active_provider = health.get("provider", provider)
    active_model = health.get("model", model)
    display_provider = get_provider_display_name(active_provider, active_model)
    has_any_key = any(bool(c.get("api_key")) for c in cfg.get("provider_configs", [cfg]))

    return {
        "ok": True,
        "enabled": enabled,
        "status": health["status"],  # 'online_llm', 'expert_offline', 'disabled', 'error'
        "is_online": health["is_online"],
        "provider": active_provider,
        "provider_display": display_provider,
        "model": active_model,
        "has_api_key": has_any_key,
        "badge_text": health["badge_text"],
        "badge_color": health["badge_color"],
        "display_name": health["display_name"],
        "description": health["description"],
        "error_detail": health.get("error_detail"),
        "mode": health["display_name"],
    }


@router.post("/health-check")
def force_health_check():
    """Принудительная повторная проверка соединения с API нейросети (без кэша)"""
    cfg = load_ai_config()
    health = verify_llm_connection(cfg, force_check=True)
    return {"ok": True, "health": health}


@router.post("/preset")
def get_preset(req: QuickPresetRequest):
    """Подбор параметров по наименованию типа объекта"""
    data = get_preset_for_building_type(req.query)
    return {"ok": True, "preset": data}


@router.post("/ask")
def ask_assistant(req: AskQuestionRequest):
    """Интеллектуальный вопрос-ответ консультант для пользователя"""
    cfg = load_ai_config()
    res = answer_assistant_question(req.question, req.contextPage or "dashboard", cfg)
    return res



@router.post("/analyze")
def analyze_object(req: AnalyzeObjectRequest, db: Session = Depends(get_db)):
    """
    Глубокий аудит объекта:
    - Загружает параметры и уже имеющиеся работы
    - Сверяет со справочником работ 123-ФЗ
    - Вызывает LLM (если настроен ключ в msg.cfg) или экспертную систему 123-ФЗ
    """
    ai_cfg = load_ai_config()
    if not ai_cfg.get("enabled", True):
        raise HTTPException(400, "ИИ-помощник отключен в конфигурации msg.cfg")

    existing_codes: List[str] = []
    target_object = None

    if req.objectId:
        target_object = db.query(Object).filter(Object.id == req.objectId).first()
        if not target_object:
            raise HTTPException(404, "Объект не найден")
        
        # Получаем назначенные работы
        assigns = db.query(Assignment).filter(
            Assignment.object_id == req.objectId,
            Assignment.status == "Активно"
        ).all()
        work_type_ids = [a.work_type_id for a in assigns if a.work_type_id]
        if work_type_ids:
            wt_rows = db.query(WorkType).filter(WorkType.id.in_(work_type_ids)).all()
            for wt in wt_rows:
                if wt.code:
                    existing_codes.append(wt.code)

        category = target_object.category or req.category or "Здание"
        fpo = getattr(target_object, "functional_hazard", None) or req.functionalHazard or "Ф3.1"
        fire_cat = getattr(target_object, "fire_hazard_category", None) or req.fireHazardCategory or "В"
        area = float(getattr(target_object, "total_area", 0.0) or req.totalArea or 0.0)
        flr = int(getattr(target_object, "floors", 1) or req.floors or 1)
    else:
        category = req.category or "Здание"
        fpo = req.functionalHazard or "Ф3.1"
        fire_cat = req.fireHazardCategory or "В"
        area = float(req.totalArea or 0.0)
        flr = int(req.floors or 1)

    catalog = db.query(WorkType).all()
    catalog_dicts = [
        {
            "code": w.code,
            "name": w.name,
            "category": w.category,
            "frequency": w.frequency,
            "price": w.price,
            "required_cert": w.required_cert,
        }
        for w in catalog
    ]

    # Проверяем реальное подключение к LLM (или цепочке провайдеров)
    health = verify_llm_connection(ai_cfg, force_check=False)
    result = None

    if health.get("is_online"):
        active_p_cfg = health.get("active_config", ai_cfg)
        # Объединяем параметры (температуру, таймаут, системный промпт)
        merged_cfg = {**ai_cfg, **active_p_cfg}
        result = call_llm_advisor(
            ai_cfg=merged_cfg,
            category=category,
            functional_hazard=fpo,
            fire_hazard_category=fire_cat,
            total_area=area,
            floors=flr,
            catalog_works=catalog_dicts,
            existing_work_codes=existing_codes,
        )

    # Резервный / дефолтный офлайн экспертный расчет 123-ФЗ
    if not result:
        result = get_expert_rules_recommendations(
            category=category,
            functional_hazard=fpo,
            fire_hazard_category=fire_cat,
            total_area=area,
            floors=flr,
            existing_work_codes=existing_codes,
        )

    # Обогащаем данными о ценах из базы
    for item in result.get("recommendations", []):
        w = next((x for x in catalog_dicts if x["code"] == item["work_code"]), None)
        if w:
            item["price"] = w["price"]
            item["duration_hours"] = w.get("duration_hours", 2)
            item["required_cert"] = w.get("required_cert", "СРО")
            item["work_type_name"] = w["name"]

    return {"ok": True, "data": result}


@router.post("/apply")
def apply_recommendations(req: ApplyRecommendationsRequest, db: Session = Depends(get_db)):
    """
    Пакетное применение рекомендаций ИИ: создание назначений и генерация графиков работ в 1 клик
    """
    target_object = db.query(Object).filter(Object.id == req.objectId).first()
    if not target_object:
        raise HTTPException(404, "Объект не найден")

    if not req.workCodes:
        raise HTTPException(400, "Не выбраны работы для назначения")

    start_d = date.fromisoformat(req.startDate) if req.startDate else date.today()
    if req.endDate:
        end_d = date.fromisoformat(req.endDate)
    else:
        # По умолчанию на 1 год вперед
        end_d = date(start_d.year + 1, start_d.month, start_d.day)

    created_assignments = []
    created_executions_total = 0

    for code in req.workCodes:
        work = db.query(WorkType).filter(WorkType.code == code).first()
        if not work:
            continue

        # Проверяем, нет ли уже активного назначения на этот вид работ
        existing = db.query(Assignment).filter(
            Assignment.object_id == target_object.id,
            Assignment.work_type_id == work.id,
            Assignment.status == "Активно"
        ).first()
        if existing:
            continue

        aid = f"ASN-{uuid.uuid4().hex[:8]}"
        dates = generate_schedule(start_d, end_d, work.frequency)
        count = len(dates)
        total_price = count * (work.price or 0)

        assign = Assignment(
            id=aid,
            object_id=target_object.id,
            work_type_id=work.id,
            start_date=start_d,
            end_date=end_d,
            frequency=work.frequency,
            total_price=total_price,
            status="Активно",
        )
        db.add(assign)

        for d in dates:
            eid = f"EXE-{uuid.uuid4().hex[:8]}"
            ex = Execution(
                id=eid,
                assignment_id=aid,
                object_id=target_object.id,
                work_type_id=work.id,
                planned_date=d,
                status="Запланировано",
            )
            db.add(ex)
            created_executions_total += 1

        created_assignments.append(work.name)

    db.commit()

    return {
        "ok": True,
        "created_assignments_count": len(created_assignments),
        "created_executions_count": created_executions_total,
        "assignments": created_assignments,
    }


class ParseTextRequest(BaseModel):
    text: str


@router.post("/import/parse-text")
def parse_organizations_text(data: ParseTextRequest):
    """
    Распознавание списка организаций/объектов из вставленного текста с помощью ИИ.
    Автоматически определяет реквизиты, классы пожарной опасности и сортирует по организациям.
    """
    res = ai_parse_organizations(data.text)
    if not res.get("ok"):
        raise HTTPException(400, res.get("error", "Не удалось распознать текст"))
    return res


@router.post("/import/parse-file")
async def parse_organizations_file(file: UploadFile = File(...)):
    """
    Распознавание списка организаций/объектов из прикреплённого файла:
    Word (DOCX, DOC), Excel (XLSX, XLS) или PDF.
    Содержимое извлекается и передаётся в ИИ для распознавания и сортировки.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(400, "Файл пуст")

    filename = file.filename or "file.bin"
    extracted_text = extract_text_from_file(contents, filename)

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(400, f"Не удалось извлечь текст из файла {filename}. Убедитесь, что файл содержит текстовые данные.")

    res = ai_parse_organizations(extracted_text)
    res["filename"] = filename
    res["text_length"] = len(extracted_text)
    return res


class BatchImportOrgsRequest(BaseModel):
    items: List[dict]
    importAs: Optional[str] = "objects"  # "objects" (объекты обслуживания) или "companies" (наши организации)


@router.post("/import/save-batch")
def save_batch_imported_orgs(data: BatchImportOrgsRequest, db: Session = Depends(get_db)):
    """
    Пакетное сохранение распознанных ИИ организаций:
    в реестр Объектов (по умолчанию) или в Организации-исполнители.
    """
    created = []
    skipped = 0
    target = data.importAs or "objects"

    for it in data.items:
        name = (it.get("name") or "").strip()
        if not name:
            skipped += 1
            continue

        if target == "companies":
            # Импорт как организация-исполнитель
            inn = "".join(ch for ch in str(it.get("inn") or "") if ch.isdigit())
            existing = db.query(Company).filter(Company.inn == inn).first() if inn else None
            if not existing:
                existing = db.query(Company).filter(Company.name == name).first()
            if existing:
                skipped += 1
                continue

            c = Company(
                id=f"COMP-{uuid.uuid4().hex[:8]}",
                name=name,
                inn=inn,
                kpp=str(it.get("kpp") or ""),
                ogrn=str(it.get("ogrn") or ""),
                address=str(it.get("address") or ""),
                phone=str(it.get("phone") or ""),
                email=str(it.get("email") or ""),
                director=str(it.get("contact_person") or ""),
                is_default=False,
            )
            db.add(c)
            created.append(name)
        else:
            # Импорт как объект защиты
            obj_id = f"OBJ-{uuid.uuid4().hex[:8]}"
            o = Object(
                id=obj_id,
                name=name,
                address=str(it.get("address") or ""),
                inn=str(it.get("inn") or ""),
                contact_person=str(it.get("contact_person") or ""),
                phone=str(it.get("phone") or ""),
                email=str(it.get("email") or ""),
                category=str(it.get("category") or "Здание"),
                functional_hazard=str(it.get("functional_hazard") or "Ф3.1"),
                fire_hazard_category=str(it.get("fire_hazard_category") or "В"),
                construction_hazard="С0",
                total_area=float(it.get("total_area") or 0.0),
                floors=int(it.get("floors") or 1),
                status="Активен",
                notes=str(it.get("notes") or ""),
            )
            db.add(o)
            created.append(name)

    db.commit()

    return {
        "ok": True,
        "target": target,
        "created_count": len(created),
        "skipped_count": skipped,
        "names": created,
    }

