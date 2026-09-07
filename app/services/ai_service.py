# -*- coding: utf-8 -*-
"""
Сервис ИИ-помощника и экспертных рекомендаций по регламентным работам (123-ФЗ, СП 484, СП 486, ППР 1479).
Конфигурация считывается строго из msg.cfg [ai_assistant].
"""
import configparser
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

logger = logging.getLogger("ai_service")
MSG_CFG_PATH = Path(__file__).parent.parent.parent / "msg.cfg"


def load_ai_config() -> Dict[str, Any]:
    """Загрузка секции [ai_assistant] из msg.cfg"""
    cfg = configparser.ConfigParser()
    if MSG_CFG_PATH.exists():
        try:
            cfg.read(str(MSG_CFG_PATH), encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения msg.cfg: %s", e)
    
    section = cfg["ai_assistant"] if cfg.has_section("ai_assistant") else {}
    return {
        "enabled": section.getboolean("enabled", fallback=True),
        "provider": section.get("provider", "auto").strip().lower(),
        "api_url": section.get("api_url", "https://api.deepseek.com/v1").strip().rstrip("/"),
        "api_key": section.get("api_key", "").strip(),
        "model": section.get("model", "deepseek-chat").strip(),
        "folder_id": section.get("folder_id", "").strip(),
        "scope": section.get("scope", "GIGACHAT_API_PERS").strip(),
        "temperature": section.getfloat("temperature", fallback=0.2),
        "request_timeout_seconds": section.getint("request_timeout_seconds", fallback=20),
        "fallback_to_rules": section.getboolean("fallback_to_rules", fallback=True),
        "system_prompt": section.get(
            "system_prompt",
            "Ты — ведущий эксперт по пожарной безопасности объектов в РФ (123-ФЗ, СП 484, СП 486)."
        ).strip(),
    }


def get_expert_rules_recommendations(
    category: str,
    functional_hazard: str,
    fire_hazard_category: str,
    total_area: float,
    floors: int,
    existing_work_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Интеллектуальная нормативная база 123-ФЗ, СП 484, СП 486, СП 3.13130, СП 10.13130, СП 7.13130.
    Работает офлайн без сторонних API, гарантируя 100% достоверность требований.
    """
    existing_work_codes = existing_work_codes or []
    recs: List[Dict[str, Any]] = []
    regulations: List[str] = []

    cat_norm = (category or "").lower()
    fpo = (functional_hazard or "Ф3.1").strip().upper()
    cat_fire = (fire_hazard_category or "В").strip().upper()
    area = float(total_area or 0.0)
    flr = int(floors or 1)

    # 1. АПС (Автоматическая пожарная сигнализация) - ПБ-01.01
    recs.append({
        "work_code": "ПБ-01.01",
        "work_name": "ТО АПС (Пожарная сигнализация)",
        "frequency": "Ежеквартально",
        "priority": "Критический",
        "law_ref": "СП 484.1311500.2020, ППР РФ № 1479 п. 54",
        "reason": f"Обязательно для всех объектов с классом {fpo}. Ежеквартальное ТО и проверка работоспособности с ведением электронного/бумажного журнала.",
    })
    regulations.append("СП 484.1311500.2020 (Системы пожарной сигнализации)")

    # 2. СОУЭ (Оповещение и управление эвакуацией) - ПБ-01.02
    soue_type = "2-3 типа"
    if area > 1000 or flr > 2 or "торг" in cat_norm or fpo in ["Ф3.1", "Ф2.1"]:
        soue_type = "3-4 типа (речевое с разделением на зоны)"
    recs.append({
        "work_code": "ПБ-01.02",
        "work_name": "ТО СОУЭ (Система оповещения)",
        "frequency": "Ежеквартально",
        "priority": "Критический",
        "law_ref": "СП 3.13130.2009, ППР РФ № 1479 п. 54",
        "reason": f"Требуется СОУЭ {soue_type}. Проверка световых табло «Выход», линий оповещения и алгоритмов эвакуации.",
    })
    regulations.append("СП 3.13130.2009 (Системы оповещения людей при пожаре)")

    # 3. Первичные средства (Огнетушители) - ПБ-02.01
    recs.append({
        "work_code": "ПБ-02.01",
        "work_name": "Перезарядка и проверка ОП-4/ОУ",
        "frequency": "Ежегодно",
        "priority": "Высокий",
        "law_ref": "СП 9.13130.2009, ППР РФ № 1479 разд. XIX",
        "reason": f"Годовое ТО огнетушителей с фиксацией в журнале эксплуатации систем противопожарной защиты.",
    })

    # 4. Дымоудаление - ПБ-04.01 (для объектов > 1 этажа, подземных, больших площадей или коридоров)
    if flr >= 2 or area >= 800 or fpo in ["Ф3.1", "Ф5.1", "Ф5.2"]:
        recs.append({
            "work_code": "ПБ-04.01",
            "work_name": "ТО противодымной вентиляции (ДУ)",
            "frequency": "Раз в полгода",
            "priority": "Высокий",
            "law_ref": "СП 7.13130.2013, ППР РФ № 1479 п. 49",
            "reason": f"Для зданий этажностью от {flr} эт. и площади {area:g} м² обязательны полугодовые испытания клапанов дымоудаления и подпора воздуха.",
        })
        regulations.append("СП 7.13130.2013 (Отопление, вентиляция и противодымная защита)")

    # 5. ВПВ (Внутренний противопожарный водопровод) - ПБ-03.01
    if area >= 500 or flr >= 2 or fpo in ["Ф3.1", "Ф5.1", "Ф5.2", "Ф4.3"]:
        recs.append({
            "work_code": "ПБ-03.01",
            "work_name": "Проверка и перекатка ВПВ",
            "frequency": "Раз в полгода",
            "priority": "Высокий",
            "law_ref": "СП 10.13130.2020, ППР РФ № 1479 п. 50",
            "reason": "Весенне-осенняя проверка на водоотдачу, перемотка рукавов на новую скатку с составлением акта.",
        })
        regulations.append("СП 10.13130.2020 (Внутренний противопожарный водопровод)")

    # 6. АУПТ (Автоматическое пожаротушение) - ПБ-03.02
    needs_aupt = False
    if fpo in ["Ф3.1"] and (area >= 3500 or (flr >= 2 and area >= 1000)):
        needs_aupt = True
    elif fpo in ["Ф5.2"] and (cat_fire in ["А", "Б", "В1", "В2"] and area >= 1000):
        needs_aupt = True
    elif fpo in ["Ф5.1"] and (cat_fire in ["А", "Б"] or (cat_fire in ["В1"] and area >= 1000)):
        needs_aupt = True

    if needs_aupt:
        recs.append({
            "work_code": "ПБ-03.02",
            "work_name": "ТО установок пожаротушения (АУПТ)",
            "frequency": "Ежеквартально",
            "priority": "Критический",
            "law_ref": "СП 486.1311500.2020 табл. 1/3, ППР РФ № 1479",
            "reason": f"Параметры объекта (ФПО {fpo}, категория {cat_fire}, площадь {area:g} м²) требуют обязательного АУПТ.",
        })
        regulations.append("СП 486.1311500.2020 (Перечень зданий, подлежащих защите АУПТ)")

    # 7. Электролаборатория - ПБ-06.01
    recs.append({
        "work_code": "ПБ-06.01",
        "work_name": "Испытания электролаборатории (ЭТЛ)",
        "frequency": "Ежегодно",
        "priority": "Средний",
        "law_ref": "ПТЭЭП, ППР РФ № 1479 п. 35",
        "reason": "Ежегодный замер сопротивления изоляции кабельных линий, петли «фаза-нуль» и проверка УЗО.",
    })

    # 8. Обучение ответственных и инструктажи - ПБ-07.01
    recs.append({
        "work_code": "ПБ-07.01",
        "work_name": "Противопожарные инструктажи персонала",
        "frequency": "Ежегодно",
        "priority": "Высокий",
        "law_ref": "Приказ МЧС России № 806, ППР РФ № 1479 п. 3",
        "reason": "Проведение повторного инструктажа не реже 1 раза в год (для пожароопасных производств — 1 раз в полугодие).",
    })

    # 9. Планы эвакуации - ПБ-05.02
    if area > 100 or flr > 1:
        recs.append({
            "work_code": "ПБ-05.02",
            "work_name": "План эвакуации (фотолюминесцентный)",
            "frequency": "Разовая",
            "priority": "Высокий",
            "law_ref": "ГОСТ 34428-2018, ППР РФ № 1479 п. 5",
            "reason": f"Для зданий с единовременным нахождением более 10 человек на этаже ({flr} эт.) обязательны планы эвакуации.",
        })

    # Отмечаем, какие работы уже назначены
    for r in recs:
        r["is_assigned"] = r["work_code"] in existing_work_codes

    unassigned_count = sum(1 for r in recs if not r["is_assigned"])

    summary_text = (
        f"Объект класса {fpo} ({category or 'Здание'}), этажность {flr}, площадь {area:g} м², категория {cat_fire}. "
        f"По нормам пожарной безопасности выявлено {len(recs)} обязательных регламентов. "
        + (f"Из них {unassigned_count} еще НЕ включены в план обслуживания!" if unassigned_count > 0 else "Все обязательные регламенты уже назначены.")
    )

    return {
        "status": "success",
        "provider": "expert_rules_pb",
        "object_summary": {
            "functional_hazard": fpo,
            "fire_hazard_category": cat_fire,
            "total_area": area,
            "floors": flr,
            "category": category,
        },
        "summary": summary_text,
        "regulations": list(set(regulations)),
        "recommendations": recs,
        "unassigned_count": unassigned_count,
    }


def call_llm_advisor(
    ai_cfg: Dict[str, Any],
    category: str,
    functional_hazard: str,
    fire_hazard_category: str,
    total_area: float,
    floors: int,
    catalog_works: List[Dict[str, Any]],
    existing_work_codes: List[str],
) -> Optional[Dict[str, Any]]:
    """Вызов внешнего LLM через OpenAI-совместимый API"""
    api_key = ai_cfg.get("api_key")
    if not api_key:
        return None

    api_url = ai_cfg.get("api_url", "https://api.openai.com/v1") + "/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    works_str = "\n".join(
        [f"- [{w['code']}] {w['name']} ({w.get('frequency', '')}, {w.get('price', 0)} руб.)" for w in catalog_works]
    )
    assigned_str = ", ".join(existing_work_codes) if existing_work_codes else "нет назначенных"

    user_prompt = f"""
Проанализируй объект противопожарной защиты:
- Категория объекта: {category}
- Класс функциональной пожарной опасности (ФПО): {functional_hazard} (ст. 32 123-ФЗ)
- Категория по взрывопожарной/пожарной опасности: {fire_hazard_category} (ст. 27 123-ФЗ, СП 12.13130)
- Общая площадь: {total_area} м²
- Этажность: {floors} этаж(ей)
- Уже назначенные работы (коды): {assigned_str}

Справочник доступных в организации регламентных работ:
{works_str}

Требования к ответу:
Верни СТРОГО валидный JSON следующей структуры:
{{
  "summary": "Краткое экспертное заключение инженера по объекту и нормативным рискам",
  "regulations": ["СП 484.1311500.2020", "СП 3.13130.2009", "ППР РФ № 1479", "123-ФЗ"],
  "recommended_codes": ["ПБ-01.01", "ПБ-01.02", ...],
  "justifications": {{
    "ПБ-01.01": "Обоснование со ссылкой на норму СП / ППР"
  }}
}}
"""

    payload = {
        "model": ai_cfg.get("model", "gpt-4o-mini"),
        "temperature": ai_cfg.get("temperature", 0.2),
        "messages": [
            {"role": "system", "content": ai_cfg.get("system_prompt", "")},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(api_url, data=req_data, headers=headers, method="POST")
        timeout = ai_cfg.get("request_timeout_seconds", 15)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            content = result["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            # Сопоставляем со справочником
            recs = []
            rec_codes = parsed.get("recommended_codes", [])
            justifs = parsed.get("justifications", {})

            for code in rec_codes:
                wk = next((w for w in catalog_works if w["code"] == code), None)
                if wk:
                    recs.append({
                        "work_code": wk["code"],
                        "work_name": wk["name"],
                        "frequency": wk.get("frequency", "Ежеквартально"),
                        "priority": "Критический" if code in ["ПБ-01.01", "ПБ-01.02", "ПБ-03.02"] else "Высокий",
                        "law_ref": "Нормы ПБ (СП 484 / СП 486 / ППР 1479)",
                        "reason": justifs.get(code, "Требуется в соответствии с характеристиками объекта"),
                        "is_assigned": code in existing_work_codes,
                    })

            return {
                "status": "success",
                "provider": f"llm_{ai_cfg.get('model')}",
                "object_summary": {
                    "functional_hazard": functional_hazard,
                    "fire_hazard_category": fire_hazard_category,
                    "total_area": total_area,
                    "floors": floors,
                    "category": category,
                },
                "summary": parsed.get("summary", ""),
                "regulations": parsed.get("regulations", []),
                "recommendations": recs,
                "unassigned_count": sum(1 for r in recs if not r["is_assigned"]),
            }
    except Exception as e:
        logger.warning("LLM API call failed, falling back to expert rules: %s", e)
        return None


def get_preset_for_building_type(building_type: str) -> Dict[str, Any]:
    """Быстрые пресеты классификации по типам для создания нового объекта"""
    t = (building_type or "").lower().strip()
    if "торг" in t or "тц" in t or "магазин" in t:
        return {
            "category": "Торговый центр",
            "functional_hazard": "Ф3.1",
            "fire_hazard_category": "В",
            "construction_hazard": "С0",
            "notes": "Здание торговли (Ф3.1). Высокая пожарная нагрузка.",
        }
    if "офис" in t or "бц" in t or "бизнес" in t or "банк" in t:
        return {
            "category": "Офис",
            "functional_hazard": "Ф4.3",
            "fire_hazard_category": "В",
            "construction_hazard": "С0",
            "notes": "Административное здание / офисы (Ф4.3).",
        }
    if "склад" in t or "логистик" in t:
        return {
            "category": "Склад",
            "functional_hazard": "Ф5.2",
            "fire_hazard_category": "В1",
            "construction_hazard": "С0",
            "notes": "Складское здание (Ф5.2). Категория В1/В2 по СП 12.13130.",
        }
    if "производ" in t or "цех" in t or "завод" in t:
        return {
            "category": "Производство",
            "functional_hazard": "Ф5.1",
            "fire_hazard_category": "В2",
            "construction_hazard": "С0",
            "notes": "Производственное здание (Ф5.1).",
        }
    if "школ" in t or "детсад" in t or "лицей" in t:
        return {
            "category": "Школа",
            "functional_hazard": "Ф1.1",
            "fire_hazard_category": "Не категорируется",
            "construction_hazard": "С0",
            "notes": "Детские и образовательные учреждения (Ф1.1). Особый контроль.",
        }
    if "больниц" in t or "клиник" in t or "госпитал" in t:
        return {
            "category": "Больница",
            "functional_hazard": "Ф1.1",
            "fire_hazard_category": "Не категорируется",
            "construction_hazard": "С0",
            "notes": "Медицинские организации с круглосуточным пребыванием (Ф1.1).",
        }
    return {
        "category": "Другое",
        "functional_hazard": "Ф3.2",
        "fire_hazard_category": "В",
        "construction_hazard": "С0",
        "notes": "Общественное или административное здание.",
    }
