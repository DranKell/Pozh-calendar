# -*- coding: utf-8 -*-
"""
Роутер ИИ-помощника: анализ объектов, подбор работ по 123-ФЗ, умные пресеты и пакетное назначение работ.
"""
from datetime import date
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.object import Object
from app.models.work_type import WorkType
from app.models.assignment import Assignment
from app.models.execution import Execution
from app.services.ai_service import (
    load_ai_config,
    get_expert_rules_recommendations,
    call_llm_advisor,
    get_preset_for_building_type,
)
from app.services.periodicity import generate_schedule

router = APIRouter()


class AnalyzeObjectRequest(BaseModel):
    objectId: Optional[str] = None
    category: Optional[str] = None
    functionalHazard: Optional[str] = "Ф3.1"
    fireHazardCategory: Optional[str] = "В"
    totalArea: Optional[float] = 0.0
    floors: Optional[int] = 1


class QuickPresetRequest(BaseModel):
    query: str


class ApplyRecommendationsRequest(BaseModel):
    objectId: str
    workCodes: List[str]
    startDate: Optional[str] = None
    endDate: Optional[str] = None


@router.get("/config")
def get_status_config():
    """Проверка конфигурации ИИ (из msg.cfg)"""
    cfg = load_ai_config()
    enabled = cfg.get("enabled", True)
    has_key = bool(cfg.get("api_key"))
    provider = cfg.get("provider", "auto")
    model = cfg.get("model", "deepseek-chat")

    if not enabled:
        status = "disabled"
        badge_text = "ИИ ВЫКЛЮЧЕН"
        badge_color = "ember"
        description = "ИИ отключен в msg.cfg (enabled=false). Заполнение данных производится ВРУЧНУЮ."
    elif has_key:
        status = "online_llm"
        badge_text = f"ОНЛАЙН: {model}"
        badge_color = "moss"
        description = f"Подключена внешняя нейросеть ({model}, провайдер: {provider})."
    else:
        status = "expert_offline"
        badge_text = "ОФЛАЙН: НОРМЫ ПБ"
        badge_color = "amber"
        description = "Внешний API-ключ не указан. Работает встроенная экспертная база регламентов и норм ПБ."

    return {
        "ok": True,
        "enabled": enabled,
        "status": status,
        "provider": provider,
        "model": model,
        "has_api_key": has_key,
        "badge_text": badge_text,
        "badge_color": badge_color,
        "description": description,
        "mode": "Нейросеть (" + model + ")" if has_key else "Экспертная система ПБ",
    }


@router.post("/preset")
def get_preset(req: QuickPresetRequest):
    """Подбор параметров по наименованию типа объекта"""
    data = get_preset_for_building_type(req.query)
    return {"ok": True, "preset": data}


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

    # Если задан API-ключ и провайдер не expert_rules, пробуем LLM
    result = None
    if ai_cfg.get("provider") != "expert_rules" and ai_cfg.get("api_key"):
        result = call_llm_advisor(
            ai_cfg=ai_cfg,
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
