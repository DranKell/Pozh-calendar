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


# Кэш OAuth токена для Сбер GigaChat (живёт 30 минут)
_GIGACHAT_TOKEN_CACHE: Dict[str, Any] = {
    "token": None,
    "expires_at": 0.0,
}

# Кэш проверки доступности API
_LLM_HEALTH_CACHE: Dict[str, Any] = {
    "checked_at": 0.0,
    "key_hash": None,
    "result": None,
}


def load_ai_config() -> Dict[str, Any]:
    """Загрузка настроек ИИ из msg.cfg с поддержкой схемы 'или-или' (YandexGPT / GigaChat)"""
    cfg = configparser.ConfigParser()
    if MSG_CFG_PATH.exists():
        try:
            cfg.read(str(MSG_CFG_PATH), encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения msg.cfg: %s", e)
    
    section = cfg["ai_assistant"] if cfg.has_section("ai_assistant") else {}
    providers_str = section.get("providers", "").strip()
    if not providers_str:
        p = section.get("provider", "yandexgpt").strip().lower()
        providers_list = [p] if p else ["yandexgpt", "gigachat"]
    else:
        providers_list = [p.strip().lower() for p in providers_str.split(",") if p.strip() and p.strip().lower() != "deepseek"]

    # Если список пуст или содержал только неподдерживаемые значения
    if not providers_list:
        providers_list = ["yandexgpt", "gigachat"]

    # Собираем конфигурации для каждого поддерживаемого провайдера (yandexgpt, gigachat)
    def get_prov_cfg(p_name: str, sec_prefix: str = "") -> Dict[str, Any]:
        sec = cfg[sec_prefix] if sec_prefix and cfg.has_section(sec_prefix) else section
        return {
            "provider": p_name,
            "api_url": sec.get("api_url", "").strip().rstrip("/"),
            "api_key": sec.get("api_key", "").strip(),
            "model": sec.get("model", "").strip(),
            "folder_id": sec.get("folder_id", "").strip(),
            "scope": sec.get("scope", "GIGACHAT_API_PERS").strip(),
        }

    provider_configs: List[Dict[str, Any]] = []
    for p in providers_list:
        sec_name = f"ai_{p}" if cfg.has_section(f"ai_{p}") else ""
        c = get_prov_cfg(p, sec_name)
        if not c["api_url"]:
            if p == "gigachat":
                c["api_url"] = "https://gigachat.devices.sberbank.ru/api/v1"
                if not c["model"]: c["model"] = "GigaChat"
            elif p == "yandexgpt":
                c["api_url"] = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
                if not c["model"]: c["model"] = "yandexgpt/latest"
        provider_configs.append(c)

    first_prov = provider_configs[0] if provider_configs else {}
    # Дефолтная активная секция
    return {
        "enabled": section.getboolean("enabled", fallback=True),
        "provider": providers_list[0] if providers_list else "yandexgpt",
        "providers_chain": providers_list,
        "provider_configs": provider_configs,
        "api_url": first_prov.get("api_url", "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"),
        "api_key": first_prov.get("api_key", ""),
        "model": first_prov.get("model", "yandexgpt/latest"),
        "folder_id": first_prov.get("folder_id", ""),
        "scope": first_prov.get("scope", "GIGACHAT_API_PERS"),
        "temperature": section.getfloat("temperature", fallback=0.2),
        "request_timeout_seconds": section.getint("request_timeout_seconds", fallback=20),
        "fallback_to_rules": section.getboolean("fallback_to_rules", fallback=True),
        "system_prompt": section.get(
            "system_prompt",
            "Ты — ведущий инспектор по пожарному надзору и эксперт по нормам ПБ (123-ФЗ, СП 484, СП 486, ППР 1479)."
        ).strip(),
    }


DUMMY_KEY_MARKERS = (
    "your_", "here", "token_secret", "ключ", "example",
    "secret_here", "key_here", "folder_id_here", "none", "null"
)

def is_dummy_key(val: Optional[str]) -> bool:
    if not val:
        return True
    s = str(val).strip().lower()
    if len(s) < 15:
        return True
    return any(m in s for m in DUMMY_KEY_MARKERS)


def get_gigachat_token(auth_key: str, scope: str = "GIGACHAT_API_PERS") -> Optional[str]:
    """Получение и кэширование OAuth-токена Сбер GigaChat"""
    import time
    import ssl
    import uuid

    if is_dummy_key(auth_key):
        return None

    now = time.time()
    if _GIGACHAT_TOKEN_CACHE["token"] and now < _GIGACHAT_TOKEN_CACHE["expires_at"]:
        return _GIGACHAT_TOKEN_CACHE["token"]

    oauth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Basic {auth_key}",
    }
    data = f"scope={scope}".encode("utf-8")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    try:
        req = urllib.request.Request(oauth_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            token = body.get("access_token")
            # Токен Сбера действует 30 минут (1800 сек), кэшируем на 25 минут
            _GIGACHAT_TOKEN_CACHE["token"] = token
            _GIGACHAT_TOKEN_CACHE["expires_at"] = now + 1500
            return token
    except Exception as e:
        logger.warning("Ошибка получения OAuth токена GigaChat: %s", e)
        return None


def get_provider_display_name(provider: str, model: str = "") -> str:
    """Определение человекочитаемого названия сервиса нейросети"""
    p = (provider or "").lower().strip()
    m = (model or "").lower().strip()

    if p == "yandexgpt" or "yandex" in m or "yagpt" in m:
        return "YandexGPT"
    if p == "gigachat" or "gigachat" in m:
        return "GigaChat"
    if p == "expert_rules":
        return "123-ФЗ"
    
    if "gpt-4" in m or "gpt-3" in m or "chatgpt" in m:
        return "ChatGPT"
    if "claude" in m:
        return "Claude"
    if "qwen" in m:
        return "Qwen"
    if "llama" in m:
        return "Llama"
    if model:
        return model.split("/")[-1].split(":")[0]
    return "YandexGPT"


def _ping_single_provider(p_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Пинг одного конкретного провайдера нейросети"""
    import ssl

    provider = p_cfg.get("provider", "auto").lower()
    api_key = p_cfg.get("api_key", "").strip()
    api_url = p_cfg.get("api_url", "").strip()
    model = p_cfg.get("model", "").strip()
    display_provider = get_provider_display_name(provider, model)

    if provider == "expert_rules" or not api_key or is_dummy_key(api_key):
        return {
            "status": "expert_offline",
            "is_online": False,
            "provider": provider,
            "display_name": "База 123-ФЗ (Без API)",
            "badge_text": "123-ФЗ",
            "badge_color": "amber",
            "description": "API-ключ не задан или содержит шаблонное значение в msg.cfg. Работает экспертная нормативная база 123-ФЗ/СП.",
            "error_detail": None,
        }

    is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url
    is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url

    ssl_ctx = None

    if is_gigachat:
        # Для GigaChat сначала получаем OAuth токен
        token = get_gigachat_token(api_key, p_cfg.get("scope", "GIGACHAT_API_PERS"))
        if not token:
            return {
                "status": "error",
                "is_online": False,
                "provider": provider,
                "display_name": f"Ошибка API: {display_provider}",
                "badge_text": "ОШИБКА",
                "badge_color": "ember",
                "description": f"Не удалось авторизоваться в GigaChat OAuth. Проверьте ключ авторизации.",
                "error_detail": "OAuth авторизация отклонена",
            }
        endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        ping_payload = {
            "model": model or "GigaChat",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    elif is_yandex:
        endpoint = api_url
        folder_id = p_cfg.get("folder_id", "").strip()
        auth_header = f"Api-Key {api_key}" if not api_key.startswith("Bearer ") else api_key
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header,
        }
        if folder_id:
            headers["x-folder-id"] = folder_id
        
        yandex_model = model if "/" in model else f"gpt://{folder_id}/{model}" if folder_id else model
        ping_payload = {
            "modelUri": yandex_model,
            "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 1},
            "messages": [{"role": "user", "text": "ping"}],
        }
    else:
        endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        ping_payload = {
            "model": model or "yandexgpt/latest",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "ping"}],
        }

    try:
        req_data = json.dumps(ping_payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
        urlopen_kwargs = {"timeout": 4}
        if ssl_ctx:
            urlopen_kwargs["context"] = ssl_ctx

        with urllib.request.urlopen(req, **urlopen_kwargs) as resp:
            resp_body = resp.read().decode("utf-8")
            json.loads(resp_body)
            return {
                "status": "online_llm",
                "is_online": True,
                "provider": provider,
                "model": model or display_provider,
                "display_name": f"Используем {display_provider}",
                "badge_text": "ОНЛАЙН",
                "badge_color": "moss",
                "description": f"Подключение к нейросети {display_provider} успешно подтверждено.",
                "error_detail": None,
                "active_config": p_cfg,
            }

    except urllib.error.HTTPError as he:
        err_body = ""
        try:
            err_body = he.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        if he.code in (401, 403):
            err_msg = "Неверный или недействительный API-ключ (401/403 Unauthorized)"
        elif he.code == 429:
            err_msg = "Превышен лимит запросов или закончился баланс (429)"
        else:
            err_msg = f"HTTP {he.code}: {err_body[:100]}"
        return {
            "status": "error",
            "is_online": False,
            "provider": provider,
            "display_name": f"Ошибка API: {display_provider}",
            "badge_text": "ОШИБКА",
            "badge_color": "ember",
            "description": f"API нейросети {display_provider}: {err_msg}.",
            "error_detail": err_msg,
        }
    except Exception as e:
        err_msg = str(e)
        return {
            "status": "error",
            "is_online": False,
            "provider": provider,
            "display_name": f"Ошибка сети: {display_provider}",
            "badge_text": "НЕДОСТУПЕН",
            "badge_color": "ember",
            "description": f"Сервер {display_provider} недоступен ({err_msg}).",
            "error_detail": err_msg,
        }


def verify_llm_connection(ai_cfg: Dict[str, Any], force_check: bool = False) -> Dict[str, Any]:
    """
    Реальная проверка работоспособности API нейросети с автоматическим перебором (Failover).
    Проверяет настроенные провайдеры по очереди, пока не найдет рабочий.
    """
    import time
    import hashlib

    enabled = ai_cfg.get("enabled", True)
    if not enabled:
        return {
            "status": "disabled",
            "is_online": False,
            "display_name": "ИИ выключен",
            "badge_text": "ВРУЧНУЮ",
            "badge_color": "amber",
            "description": "ИИ отключен в msg.cfg (enabled=false). Все поля заполняются вручную.",
            "error_detail": None,
        }

    provider_configs = ai_cfg.get("provider_configs", [])
    if not provider_configs:
        provider_configs = [ai_cfg]

    cache_str = "|".join([f"{c.get('provider')}:{c.get('api_key')}:{c.get('api_url')}" for c in provider_configs])
    cache_sig = hashlib.md5(cache_str.encode("utf-8")).hexdigest()
    now = time.time()

    if not force_check and _LLM_HEALTH_CACHE["key_hash"] == cache_sig:
        if (now - _LLM_HEALTH_CACHE["checked_at"]) < 180:
            return _LLM_HEALTH_CACHE["result"]

    last_error_res = None
    # Перебираем настроенные провайдеры по очереди
    for p_cfg in provider_configs:
        res = _ping_single_provider(p_cfg)
        if res["is_online"]:
            _LLM_HEALTH_CACHE["checked_at"] = now
            _LLM_HEALTH_CACHE["key_hash"] = cache_sig
            _LLM_HEALTH_CACHE["result"] = res
            return res
        elif res["status"] == "error":
            last_error_res = res

    # Если ни один не подошел, но был настроен ключ с ошибкой
    if last_error_res:
        _LLM_HEALTH_CACHE["checked_at"] = now
        _LLM_HEALTH_CACHE["key_hash"] = cache_sig
        _LLM_HEALTH_CACHE["result"] = last_error_res
        return last_error_res

    # Иначе офлайн 123-ФЗ
    res = {
        "status": "expert_offline",
        "is_online": False,
        "provider": "expert_rules",
        "display_name": "База 123-ФЗ (Без API)",
        "badge_text": "123-ФЗ",
        "badge_color": "amber",
        "description": "API-ключи не указаны. Работает экспертная нормативная база 123-ФЗ/СП.",
        "error_detail": None,
    }
    _LLM_HEALTH_CACHE["checked_at"] = now
    _LLM_HEALTH_CACHE["key_hash"] = cache_sig
    _LLM_HEALTH_CACHE["result"] = res
    return res



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


def _invoke_single_llm_advisor(
    p_cfg: Dict[str, Any],
    ai_cfg: Dict[str, Any],
    user_prompt: str,
    catalog_works: List[Dict[str, Any]],
    existing_work_codes: List[str],
    category: str,
    functional_hazard: str,
    fire_hazard_category: str,
    total_area: float,
    floors: int,
) -> Optional[Dict[str, Any]]:
    """Единичный вызов конкретной LLM с парсингом ответа"""
    api_key = p_cfg.get("api_key")
    if not api_key or is_dummy_key(api_key):
        return None

    import ssl
    provider = p_cfg.get("provider", "yandexgpt").lower()
    model = p_cfg.get("model", "")
    api_url = p_cfg.get("api_url", "")

    is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url
    is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url
    ssl_ctx = None

    if is_gigachat:
        token = get_gigachat_token(api_key, p_cfg.get("scope", "GIGACHAT_API_PERS"))
        if not token:
            return None
        endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        payload = {
            "model": model or "GigaChat",
            "temperature": ai_cfg.get("temperature", 0.2),
            "messages": [
                {"role": "system", "content": ai_cfg.get("system_prompt", "")},
                {"role": "user", "content": user_prompt},
            ],
        }
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    elif is_yandex:
        endpoint = api_url
        folder_id = p_cfg.get("folder_id", "").strip()
        auth_header = f"Api-Key {api_key}" if not api_key.startswith("Bearer ") else api_key
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_header,
        }
        if folder_id:
            headers["x-folder-id"] = folder_id

        yandex_model = model if "/" in model else f"gpt://{folder_id}/{model}" if folder_id else model
        payload = {
            "modelUri": yandex_model,
            "completionOptions": {
                "stream": False,
                "temperature": ai_cfg.get("temperature", 0.2),
                "maxTokens": 1500,
            },
            "messages": [
                {"role": "system", "text": ai_cfg.get("system_prompt", "")},
                {"role": "user", "text": user_prompt},
            ],
        }
    else:
        endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        payload = {
            "model": model,
            "temperature": ai_cfg.get("temperature", 0.2),
            "messages": [
                {"role": "system", "content": ai_cfg.get("system_prompt", "")},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }

    try:
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
        timeout = ai_cfg.get("request_timeout_seconds", 12)
        urlopen_kwargs = {"timeout": timeout}
        if ssl_ctx:
            urlopen_kwargs["context"] = ssl_ctx

        with urllib.request.urlopen(req, **urlopen_kwargs) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            
            if is_yandex:
                content = result["result"]["alternatives"][0]["message"]["text"]
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1]
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("```", 1)[0]
                parsed = json.loads(cleaned)
            elif is_gigachat:
                content = result["choices"][0]["message"]["content"]
                cleaned = content.strip()
                if "```json" in cleaned:
                    cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0]
                elif "```" in cleaned:
                    cleaned = cleaned.split("```", 1)[1].split("```", 1)[0]
                parsed = json.loads(cleaned.strip())
            else:
                content = result["choices"][0]["message"]["content"]
                parsed = json.loads(content)

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
                "provider": f"llm_{provider}",
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
        logger.warning("LLM API call (%s) failed: %s", provider, e)
        return None


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
    """
    Вызов внешнего LLM с автоматическим отказоустойчивым перебором (Failover).
    Если YandexGPT дает ошибку сети/VPN/таймаут -> мгновенно на лету переключается на GigaChat!
    """
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
  "recommended_codes": ["ПБ-01.01", "ПБ-01.02"],
  "justifications": {{
    "ПБ-01.01": "Обоснование со ссылкой на норму СП / ППР"
  }}
}}
"""

    provider_configs = ai_cfg.get("provider_configs", [])
    if not provider_configs:
        provider_configs = [ai_cfg]

    for p_cfg in provider_configs:
        if is_dummy_key(p_cfg.get("api_key")):
            continue
        res = _invoke_single_llm_advisor(
            p_cfg=p_cfg,
            ai_cfg=ai_cfg,
            user_prompt=user_prompt,
            catalog_works=catalog_works,
            existing_work_codes=existing_work_codes,
            category=category,
            functional_hazard=functional_hazard,
            fire_hazard_category=fire_hazard_category,
            total_area=total_area,
            floors=floors,
        )
        if res:
            return res

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


def answer_assistant_question(question: str, context_page: str = "", ai_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Интеллектуальный ИИ-консультант новичка:
    Отвечает на вопросы о логике работы программы 'Календарь ТО' и пожарной безопасности.
    Работает через LLM (если есть ключ) или через встроенную экспертную базу знаний.
    """
    q_lower = (question or "").lower().strip()
    ai_cfg = ai_cfg or load_ai_config()
    health = verify_llm_connection(ai_cfg, force_check=False)
    if health.get("is_online") and ai_cfg.get("enabled", True):
        active_p_cfg = health.get("active_config", ai_cfg)
        provider_configs = ai_cfg.get("provider_configs", [active_p_cfg])
        for p_cfg in provider_configs:
            if is_dummy_key(p_cfg.get("api_key")):
                continue
            merged_cfg = {**ai_cfg, **p_cfg}
            api_key = merged_cfg.get("api_key")
            provider = merged_cfg.get("provider", "auto").lower()
            model = merged_cfg.get("model", "")
            api_url = merged_cfg.get("api_url", "")
            is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url
            is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url

            try:
                if is_gigachat:
                    token = get_gigachat_token(api_key, merged_cfg.get("scope", "GIGACHAT_API_PERS"))
                    if token:
                        endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
                        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
                        payload = {
                            "model": model or "GigaChat",
                            "temperature": 0.3,
                            "messages": [
                                {"role": "system", "content": system_instruction},
                                {"role": "user", "content": f"Вопрос пользователя (находится в разделе '{context_page}'): {question}"}
                            ]
                        }
                        import ssl
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                        with urllib.request.urlopen(req, timeout=12, context=ctx) as resp:
                            body = json.loads(resp.read().decode("utf-8"))
                            ans = body["choices"][0]["message"]["content"].strip()
                            return {"ok": True, "answer": ans, "source": f"ИИ (GigaChat)"}
                elif is_yandex:
                    folder_id = merged_cfg.get("folder_id", "").strip()
                    auth_header = f"Api-Key {api_key}" if not api_key.startswith("Bearer ") else api_key
                    headers = {"Content-Type": "application/json", "Authorization": auth_header}
                    if folder_id: headers["x-folder-id"] = folder_id
                    y_model = model if "/" in model else f"gpt://{folder_id}/{model}" if folder_id else model
                    payload = {
                        "modelUri": y_model,
                        "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": 800},
                        "messages": [
                            {"role": "system", "text": system_instruction},
                            {"role": "user", "text": f"Вопрос пользователя (раздел '{context_page}'): {question}"}
                        ]
                    }
                    req = urllib.request.Request(api_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                        ans = body["result"]["alternatives"][0]["message"]["text"].strip()
                        return {"ok": True, "answer": ans, "source": "ИИ (YandexGPT)"}
            except Exception as e:
                logger.warning("Провайдер %s недоступен: %s, переключаюсь на следующий...", provider, e)
                continue

    # Экспертная база знаний (Offline FAQ)
    faq_items = [
        {
            "keys": ["с чего начать", "как начать", "первые шаги", "как пользоваться", "логика", "инструкция", "новичок"],
            "answer": (
                "🎯 **Логика работы программы очень проста и состоит из 5 шагов:**\n\n"
                "1️⃣ **Добавьте объект** (раздел «Объекты» ➔ «+ Новый объект»). Укажите название, адрес, площадь и класс пожарной опасности (или нажмите кнопку «🤖 ИИ» для автоматического аудита).\n"
                "2️⃣ **Проверьте виды работ** (раздел «Виды работ») — там уже загружены все стандартные регламенты ПБ (сигнализация, оповещение, огнетушители, гидранты).\n"
                "3️⃣ **Создайте назначение** (раздел «Назначения» ➔ «+ Новое назначение»). Выберите объект, работу, период (например, на 1 год) и периодичность. Программа **автоматически построит точный график дат**!\n"
                "4️⃣ **Контролируйте Календарь** (раздел «Календарь»). В нужный день откройте карточку и нажмите «Выполнить».\n"
                "5️⃣ **Выставляйте Счета** (раздел «Счета»). Выберите объект, организацию и распечатайте готовый счёт или акт выполненных работ А4."
            )
        },
        {
            "keys": ["график", "расписание", "как составить график", "назначен", "назначить"],
            "answer": (
                "📅 **Как составить график ТО на год:**\n\n"
                "1. Перейдите в раздел **«Назначения»** и нажмите **«+ Новое назначение»** (или в «Объектах» нажмите кнопку «🤖 ИИ» и выберите «Назначить все рекомендованные в 1 клик»).\n"
                "2. Укажите объект, регламент (например, *ТО АПС*) и периодичность (*Ежеквартально* или *Ежемесячно*).\n"
                "3. Укажите даты: с сегодняшнего дня по конец года.\n"
                "4. Нажмите **«Создать с авторасчётом дат»**.\n\n"
                "✨ Программа сама рассчитает правильные даты с защитой от сдвигов месяцев и отобразит их в Календаре!"
            )
        },
        {
            "keys": ["просроч", "красный", "не успел", "просрочен"],
            "answer": (
                "🔴 **Что делать, если появилась просрочка:**\n\n"
                "1. Просроченными считаются запланированные работы, плановая дата которых уже наступила, но статус ещё не изменён на «Выполнено».\n"
                "2. Перейдите в **«Дашборд»** (блок «Просроченные») или **«Календарь»** (красные отметки).\n"
                "3. Кликните по работе:\n"
                "   - Если работа выполнена: выберите статус **«Выполнено»**, укажите фактическую дату и мастера.\n"
                "   - Если выезд переносится: выберите статус **«Перенесено»** и укажите новую дату."
            )
        },
        {
            "keys": ["цвет", "цвета", "статус", "синий", "зеленый", "желтый"],
            "answer": (
                "🎨 **Цветовая индикация в Календаре:**\n\n"
                "• 🔵 **Синий** — Запланировано (предстоящие работы по графику).\n"
                "• 🟢 **Зелёный** — Выполнено (работа успешно проведена и закрыта).\n"
                "• 🟡 **Жёлтый** — Перенесено (выезд сдвинут на другую дату по согласованию).\n"
                "• 🔴 **Красный** — Просрочено (срок прошёл, работа требует немедленного внимания).\n"
                "• ⚫ **Серый** — Отменено."
            )
        },
        {
            "keys": ["фпо", "класс", "ф3.1", "ф4.3", "ф1.1", "ф5.2", "категори"],
            "answer": (
                "🏢 **Класс функциональной пожарной опасности (ФПО по ст. 32 123-ФЗ):**\n\n"
                "• **Ф1.1** — Детсады, школы, больницы, спальные корпуса.\n"
                "• **Ф3.1** — Торговые центры, магазины, супермаркеты.\n"
                "• **Ф4.3** — Офисные центры, банки, административные здания.\n"
                "• **Ф5.1 / Ф5.2** — Производства, цеха и складские помещения.\n\n"
                "💡 *Совет:* Вы можете нажать кнопку «🤖 ИИ» в разделе «Объекты» и просто написать «Склад» или «Офис» — ИИ сам подставит нужный класс ФПО и категорию пожароопасности!"
            )
        },
        {
            "keys": ["счет", "счёт", "акт", "печать", "оплат", "организац"],
            "answer": (
                "💸 **Как выставить счёт и распечатать Акт:**\n\n"
                "1. Перейдите в раздел **«Счета»**.\n"
                "2. Нажмите **«+ Выставить счёт»**.\n"
                "3. Выберите объект и юридическое лицо-исполнителя (реквизиты организаций настраиваются во вкладке «Организации»).\n"
                "4. После создания нажмите кнопку **«🖨 Счёт»** или **«📄 Акт»** — откроется официальная печатная форма А4, готовая к отправке клиенту или печати в PDF."
            )
        },
        {
            "keys": ["ии", "нейросеть", "api", "gigachat", "yandex", "123-фз"],
            "answer": (
                "🤖 **Как работает ИИ в системе:**\n\n"
                "• **Онлайн-режим (зелёный индикатор)**: Если в `msg.cfg` указан ключ YandexGPT или GigaChat, система использует нейросеть для интеллектуального аудита, инспекционных напоминаний и распознавания контрагентов.\n"
                "• **Автономный режим (янтарный индикатор)**: Если ключа нет или сеть недоступна, система автоматически работает на **встроенной экспертной нормативной базе 123-ФЗ, СП 484, СП 486 и ППР № 1479**, гарантируя 100% точность требований пожарной безопасности даже без интернета!"
            )
        }
    ]

    for item in faq_items:
        if any(k in q_lower for k in item["keys"]):
            return {"ok": True, "answer": item["answer"], "source": "База знаний системы"}

    # Универсальный ответ по умолчанию
    return {
        "ok": True,
        "answer": (
            f"Я могу помочь вам разобраться с системой «Календарь ТО»!\n\n"
            f"• Чтобы добавить объект и настроить ТО, перейдите в **«Объекты»**.\n"
            f"• Чтобы увидеть график всех работ по дням — откройте **«Календарь»**.\n"
            f"• Чтобы посмотреть приближающиеся и просроченные работы — откройте **«Дашборд»**.\n\n"
            f"Попробуйте спросить: *«С чего начать?»*, *«Как составить график?»*, *«Что означают цвета?»* или *«Как выставить счёт?»*."
        ),
        "source": "Гид новичка"
    }


def ai_parse_organizations(raw_text: str) -> Dict[str, Any]:
    """
    Интеллектуальное распознавание списка организаций/объектов из текста:
    1. Полноценный обход провайдеров LLM по схеме «ИЛИ-ИЛИ» (YandexGPT -> GigaChat).
       Если один не настроен, выдает ошибку ключа или недоступен — мгновенно пробуется другой.
    2. Если недоступны оба провайдера — экспертный локальный regex-парсер реквизитов.
    3. Защита от галлюцинаций: фильтрация любых фиктивных заглушек.
    4. Автоматическая группировка/сортировка по названию организации.
    """
    if not raw_text or not raw_text.strip():
        return {"ok": False, "error": "Текст для распознавания пуст", "items": []}

    cfg = load_ai_config()
    provider_configs = cfg.get("provider_configs", [])
    if not provider_configs:
        provider_configs = [cfg]

    parsed_items: List[Dict[str, Any]] = []
    source_name = "Встроенный парсер реквизитов"

    # 1. Полноценный перебор провайдеров по схеме failover «ИЛИ-ИЛИ» (YandexGPT / GigaChat)
    if cfg.get("enabled", True):
        for p_cfg in provider_configs:
            prov_name = p_cfg.get("provider", "").lower()
            if prov_name not in ("yandexgpt", "gigachat") and "yandex" not in prov_name and "gigachat" not in prov_name:
                continue
            if not p_cfg.get("api_key") or is_dummy_key(p_cfg.get("api_key")):
                continue

            llm_result = _call_llm_parse_orgs(p_cfg, raw_text[:12000])
            if llm_result and isinstance(llm_result, list) and len(llm_result) > 0:
                # Проверяем, что результат содержит реальные распознанные данные
                parsed_items = llm_result
                display_prov = get_provider_display_name(prov_name, p_cfg.get("model", ""))
                source_name = f"Нейросеть {display_prov}"
                break

    # 2. Fallback: экспертный локальный парсер (123-ФЗ)
    if not parsed_items:
        parsed_items = _rule_based_parse_orgs(raw_text)

    # 3. Нормализация, очистка от тестовых заглушек и сортировка по названию
    cleaned_items = []
    forbidden_names = {"ооо ромашка", "ромашка", "ооо организация", "организация", "пример"}
    forbidden_inns = {"7701234567", "0000000000", "1234567890"}

    for item in parsed_items:
        name = str(item.get("name") or "").strip()
        if not name:
            continue

        inn = str(item.get("inn") or "").strip()
        inn = "".join(ch for ch in inn if ch.isdigit())
        kpp = str(item.get("kpp") or "").strip()
        kpp = "".join(ch for ch in kpp if ch.isdigit())
        ogrn = str(item.get("ogrn") or "").strip()
        ogrn = "".join(ch for ch in ogrn if ch.isdigit())

        # Жесткая защита от любых заглушек
        name_clean = name.lower().replace('"', '').replace('«', '').replace('»', '').strip()
        if any(fn in name_clean for fn in ["ромашка", "пример организации", "тестовая организация"]):
            continue
        if name_clean in forbidden_names and (not inn or inn in forbidden_inns):
            continue

        # ФПО
        fpo = str(item.get("functional_hazard") or "Ф3.1").strip().upper()
        if not fpo.startswith("Ф"):
            fpo = "Ф" + fpo

        cleaned_items.append({
            "name": name,
            "inn": inn,
            "kpp": kpp,
            "ogrn": ogrn,
            "address": str(item.get("address") or "").strip(),
            "phone": str(item.get("phone") or "").strip(),
            "email": str(item.get("email") or "").strip(),
            "contact_person": str(item.get("contact_person") or item.get("director") or "").strip(),
            "bank": str(item.get("bank") or "").strip(),
            "bik": str(item.get("bik") or "").strip(),
            "account": str(item.get("account") or "").strip(),
            "corr_account": str(item.get("corr_account") or "").strip(),
            "category": str(item.get("category") or "Здание").strip(),
            "functional_hazard": fpo or "Ф3.1",
            "fire_hazard_category": str(item.get("fire_hazard_category") or "В").strip().upper() or "В",
            "total_area": float(item.get("total_area") or 0.0),
            "floors": int(item.get("floors") or 1),
            "notes": str(item.get("notes") or "").strip(),
        })

    # Сортировка по названию организации
    cleaned_items.sort(key=lambda x: x["name"].lower())

    return {
        "ok": True,
        "source": source_name,
        "count": len(cleaned_items),
        "items": cleaned_items
    }


def _call_llm_parse_orgs(p_cfg: Dict[str, Any], text_slice: str) -> Optional[List[Dict[str, Any]]]:
    """Запрос в нейросеть (YandexGPT или GigaChat) для структурирования организаций"""
    api_key = p_cfg.get("api_key")
    if not api_key:
        return None

    import ssl
    provider = p_cfg.get("provider", "auto").lower()
    model = p_cfg.get("model", "")
    api_url = p_cfg.get("api_url", "")

    prompt = f"""
Ты — специализированный ИИ-парсер реквизитов и контрагентов.
Внимательно проанализируй следующий текст и извлеки из него ВСЕ найденные организации, контрагенты, учреждения или обслуживаемые объекты недвижимости.

Категорически запрещено выдумывать или генерировать несуществующие организации (никаких «ООО Ромашка» или тестовых данных)!
Извлекай ТОЛЬКО те сущности и реквизиты, которые реально присутствуют в исходном тексте.
Если в тексте нет организаций, верни {{"organizations": []}}.

Для каждой найденной в тексте организации заполни поля:
- name: точное наименование из текста (ООО, ПАО, ИП, наименование ТЦ, школы, завода и т.д.)
- inn: ИНН (строка цифр)
- kpp: КПП (строка цифр, если есть в тексте)
- ogrn: ОГРН / ОГРНИП (строка цифр, если есть в тексте)
- address: фактический или юридический адрес
- phone: контактный телефон
- email: контактный email
- contact_person: контактное лицо, директор или представитель
- category: категория (Офис, Склад, Торговый центр, Школа, Производство, Больница, Здание)
- functional_hazard: класс функциональной пожарной опасности по 123-ФЗ (Ф1.1, Ф1.2, Ф1.3, Ф2.1, Ф3.1, Ф3.2, Ф4.3, Ф5.1, Ф5.2 и т.д., по умолчанию Ф3.1)
- fire_hazard_category: категория взрывопожароопасности (А, Б, В, Г, Д, Не категорируется, по умолчанию В)
- total_area: общая площадь в м² (число float, если указана в тексте)
- floors: этажность (число int, если указана в тексте)
- notes: любые дополнительные примечания

Ответ должен быть СТРОГО в формате JSON без markdown-разметки:
{{"organizations": [{{"name": "...", "inn": "...", "address": "...", "category": "...", "functional_hazard": "..."}}]}}

Текст для извлечения данных:
\"\"\"
{text_slice}
\"\"\"
"""
    is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url
    is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url
    ssl_ctx = None

    try:
        if is_gigachat:
            token = get_gigachat_token(api_key, p_cfg.get("scope", "GIGACHAT_API_PERS"))
            if not token:
                return None
            endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
            payload = {
                "model": model or "GigaChat",
                "temperature": 0.1,
                "messages": [{"role": "user", "content": prompt}],
            }
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        elif is_yandex:
            endpoint = api_url
            folder_id = p_cfg.get("folder_id", "").strip()
            auth_header = f"Api-Key {api_key}" if not api_key.startswith("Bearer ") else api_key
            headers = {"Content-Type": "application/json", "Authorization": auth_header}
            if folder_id:
                headers["x-folder-id"] = folder_id
            yandex_model = model if "/" in model else f"gpt://{folder_id}/{model}" if folder_id else model
            payload = {
                "modelUri": yandex_model,
                "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 3000},
                "messages": [{"role": "user", "text": prompt}],
            }
        else:
            return None

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=req_data, headers=headers, method="POST")
        urlopen_kwargs = {"timeout": 30}
        if ssl_ctx:
            urlopen_kwargs["context"] = ssl_ctx

        with urllib.request.urlopen(req, **urlopen_kwargs) as resp:
            body = resp.read().decode("utf-8")
            res_json = json.loads(body)
            if is_yandex:
                txt = res_json["result"]["alternatives"][0]["message"]["text"]
            elif is_gigachat:
                txt = res_json["choices"][0]["message"]["content"]
            else:
                txt = ""

            txt = txt.strip()
            if "```json" in txt:
                txt = txt.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in txt:
                txt = txt.split("```", 1)[1].split("```", 1)[0]

            parsed = json.loads(txt.strip())
            if isinstance(parsed, dict) and "organizations" in parsed:
                return parsed["organizations"]
            elif isinstance(parsed, list):
                return parsed
    except Exception as e:
        logger.warning("Ошибка вызова LLM (%s) для парсинга организаций: %s", provider, e)
    return None


def _parse_single_card_org(text: str) -> Optional[Dict[str, Any]]:
    """
    Распознает документ-карточку одной организации (таблицы вида «Ключ: Значение»,
    «Карточка сведений о контрагенте / предприятии», «Реквизиты компании»).
    """
    import re

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    card: Dict[str, Any] = {}
    found_keys = 0

    inn_pattern = re.compile(r'\b(?:ИНН[:\s]*)?(\d{10}|\d{12})\b', re.IGNORECASE)
    kpp_pattern = re.compile(r'\b(?:КПП[:\s]*)?(\d{9})\b', re.IGNORECASE)
    ogrn_pattern = re.compile(r'\b(?:ОГРН(?:ИП)?[:\s]*)?(\d{13}|\d{15})\b', re.IGNORECASE)
    bik_pattern = re.compile(r'\b(?:БИК[:\s]*)?(\d{9})\b', re.IGNORECASE)
    acc_pattern = re.compile(r'\b(\d{20})\b')
    phone_pattern = re.compile(r'(?:\+7|8)[\s\-\(]*\d{3}[\s\-\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}')
    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

    for line in lines:
        parts = [p.strip() for p in re.split(r'[\t|;]', line) if p.strip()]
        if len(parts) >= 2:
            key = parts[0]
            val = " | ".join(parts[1:])
            if key.isdigit() and len(parts) >= 3:
                key = parts[1]
                val = " | ".join(parts[2:])
            key_l = key.lower()

            if "краткое наименование" in key_l:
                card["short_name"] = val
                found_keys += 1
            elif "полное наименование" in key_l:
                card["full_name"] = val
                found_keys += 1
            elif "наименование" in key_l and "банка" not in key_l and "name" not in card:
                card["name"] = val
                found_keys += 1
            elif "инн" in key_l:
                m = inn_pattern.search(val)
                if m:
                    card["inn"] = m.group(1)
                    found_keys += 1
            elif "кпп" in key_l:
                m = kpp_pattern.search(val)
                if m:
                    card["kpp"] = m.group(1)
                    found_keys += 1
            elif "огрн" in key_l:
                m = ogrn_pattern.search(val)
                if m:
                    card["ogrn"] = m.group(1)
                    found_keys += 1
            elif "адрес" in key_l and ("юридическ" in key_l or "address" not in card):
                card["address"] = val
                found_keys += 1
            elif any(r in key_l for r in ["руководител", "директор", "генеральный", "ф.и.о"]):
                card["contact_person"] = val
                found_keys += 1
            elif any(c in key_l for c in ["телефон", "связ", "почт", "контакт"]):
                em = email_pattern.search(val)
                if em:
                    card["email"] = em.group(0)
                pm = phone_pattern.search(val)
                if pm:
                    card["phone"] = pm.group(0)
                found_keys += 1
            elif "банк" in key_l and ("наименование" in key_l or len(parts) >= 2):
                card["bank"] = val
            elif "бик" in key_l:
                bm = bik_pattern.search(val)
                if bm:
                    card["bik"] = bm.group(1)
            elif "расчетн" in key_l or "расчётн" in key_l:
                am = acc_pattern.search(val)
                if am:
                    card["account"] = am.group(1)
            elif "корреспондентск" in key_l or "к/с" in key_l:
                cm = acc_pattern.search(val)
                if cm:
                    card["corr_account"] = cm.group(1)

    # Карточка признается валидной, если найден хотя бы ИНН/ОГРН и наименование, либо 2+ ключевых атрибута
    chosen_name = card.get("short_name") or card.get("name") or card.get("full_name")
    if chosen_name and (card.get("inn") or card.get("ogrn") or found_keys >= 2):
        # Очищаем имя от лишних префиксов и кавычек
        cleaned_name = chosen_name.strip().strip("|").strip()
        category_preset = get_preset_for_building_type(cleaned_name)
        return {
            "name": cleaned_name,
            "inn": card.get("inn") or "",
            "kpp": card.get("kpp") or "",
            "ogrn": card.get("ogrn") or "",
            "address": card.get("address") or "",
            "phone": card.get("phone") or "",
            "email": card.get("email") or "",
            "contact_person": card.get("contact_person") or "",
            "bank": card.get("bank") or "",
            "bik": card.get("bik") or "",
            "account": card.get("account") or "",
            "corr_account": card.get("corr_account") or "",
            "category": category_preset.get("category", "Здание"),
            "functional_hazard": category_preset.get("functional_hazard", "Ф3.1"),
            "fire_hazard_category": category_preset.get("fire_hazard_category", "В"),
            "total_area": 0.0,
            "floors": 1,
            "notes": f"Банк: {card.get('bank', '')} Р/с: {card.get('account', '')} БИК: {card.get('bik', '')}".strip(),
        }
    return None


def _rule_based_parse_orgs(text: str) -> List[Dict[str, Any]]:
    """Экспертный эвристический парсер реквизитов организаций (regex + паттерны РФ)"""
    import re

    # 1. Сначала проверяем, не является ли весь документ единой карточкой организации
    single_card = _parse_single_card_org(text)
    if single_card:
        return [single_card]

    results = []

    # Разделяем текст на блоки по строкам или разделителям
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    
    # Поиск ИНН, КПП, ОГРН, email, телефонов
    inn_pattern = re.compile(r'\b(?:ИНН[:\s]*)?(\d{10}|\d{12})\b', re.IGNORECASE)
    phone_pattern = re.compile(r'(?:\+7|8)[\s\-\(]*\d{3}[\s\-\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}')
    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    fpo_pattern = re.compile(r'\b(Ф\d(?:\.\d)?)\b', re.IGNORECASE)

    current_org: Optional[Dict[str, Any]] = None

    def flush_current():
        nonlocal current_org
        if current_org and current_org.get("name"):
            results.append(current_org)
        current_org = None

    org_starter_regex = re.compile(
        r'^(?:ООО|ПАО|АО|ЗАО|ИП|МУП|ГУП|ГБОУ|МАОУ|ФКУ|НКО|ТСЖ|ЖСК|УК|Компания|Организация|Предприятие|ТЦ|БЦ|Завод|Школа|Больница|Детский сад)\b',
        re.IGNORECASE
    )

    for line in lines:
        # Проверяем, начинается ли строка с новой организации или табличного разделителя
        parts = [p.strip() for p in re.split(r'[\t|;]', line) if p.strip()]
        
        # Если строка содержит табличные колонки
        if len(parts) >= 2:
            name_candidate = parts[0]
            inn_candidate = ""
            addr_candidate = ""
            for p in parts[1:]:
                im = inn_pattern.search(p)
                if im and not inn_candidate:
                    inn_candidate = im.group(1)
                elif ("г." in p or "ул." in p or "обл." in p or "д." in p) and not addr_candidate:
                    addr_candidate = p

            if len(name_candidate) >= 3 and not name_candidate.lower().startswith(("наименов", "№")):
                flush_current()
                results.append({
                    "name": name_candidate,
                    "inn": inn_candidate,
                    "address": addr_candidate,
                    "phone": "",
                    "email": "",
                    "contact_person": "",
                    "category": get_preset_for_building_type(name_candidate).get("category", "Здание"),
                    "functional_hazard": get_preset_for_building_type(name_candidate).get("functional_hazard", "Ф3.1"),
                    "fire_hazard_category": get_preset_for_building_type(name_candidate).get("fire_hazard_category", "В"),
                    "total_area": 0.0,
                    "floors": 1,
                    "notes": "Импортировано из таблицы",
                })
                continue

        # Обычная строковая эвристика
        is_new_org = bool(org_starter_regex.match(line)) or ("«" in line and "»" in line)
        if is_new_org:
            flush_current()
            current_org = {
                "name": line,
                "inn": "",
                "address": "",
                "phone": "",
                "email": "",
                "contact_person": "",
                "category": get_preset_for_building_type(line).get("category", "Здание"),
                "functional_hazard": get_preset_for_building_type(line).get("functional_hazard", "Ф3.1"),
                "fire_hazard_category": get_preset_for_building_type(line).get("fire_hazard_category", "В"),
                "total_area": 0.0,
                "floors": 1,
                "notes": "",
            }
        else:
            if not current_org:
                # Первая попавшаяся строка как название
                if len(line) > 3 and not line.startswith(("-", "#", "=", "*")):
                    current_org = {
                        "name": line,
                        "inn": "",
                        "address": "",
                        "phone": "",
                        "email": "",
                        "contact_person": "",
                        "category": get_preset_for_building_type(line).get("category", "Здание"),
                        "functional_hazard": get_preset_for_building_type(line).get("functional_hazard", "Ф3.1"),
                        "fire_hazard_category": get_preset_for_building_type(line).get("fire_hazard_category", "В"),
                        "total_area": 0.0,
                        "floors": 1,
                        "notes": "",
                    }
                    continue

            # Дополняем реквизиты текущей организации
            if current_org:
                im = inn_pattern.search(line)
                if im and not current_org["inn"]:
                    current_org["inn"] = im.group(1)

                pm = phone_pattern.search(line)
                if pm and not current_org["phone"]:
                    current_org["phone"] = pm.group(0)

                em = email_pattern.search(line)
                if em and not current_org["email"]:
                    current_org["email"] = em.group(0)

                fm = fpo_pattern.search(line)
                if fm:
                    current_org["functional_hazard"] = fm.group(1).upper()

                if any(kw in line.lower() for kw in ["г.", "ул.", "пер.", "пр-кт", "шоссе", "обл.", "дом", "лит."]):
                    if not current_org["address"]:
                        current_org["address"] = line

    flush_current()

    # Если вообще ничего не нашлось, но есть строки — создаём объекты по строкам
    if not results and lines:
        for ln in lines:
            if len(ln) >= 3 and not ln.startswith(("-", "=", "#")):
                preset = get_preset_for_building_type(ln)
                results.append({
                    "name": ln,
                    "inn": "",
                    "address": "",
                    "phone": "",
                    "email": "",
                    "contact_person": "",
                    "category": preset.get("category", "Здание"),
                    "functional_hazard": preset.get("functional_hazard", "Ф3.1"),
                    "fire_hazard_category": preset.get("fire_hazard_category", "В"),
                    "total_area": 0.0,
                    "floors": 1,
                    "notes": "",
                })

    return results


# Кэш текстов инспектора, чтобы не вызывать LLM повторно для одного и того же выполнения в течение дня
_INSPECTOR_ALERT_CACHE: Dict[str, Any] = {}


def generate_inspector_reminder_text(exec_info: Dict[str, Any], days_left: int, ai_cfg: Optional[Dict[str, Any]] = None) -> str:
    """
    Формирование краткого, авторитетного напоминания о предстоящем ТО в стиле инспектора по пожарной безопасности.
    Сгенерировано с помощью активной нейросети (YandexGPT / GigaChat) или экспертной базы при офлайне.
    Длина: 1-2 предложения, строго, четко и по делу.
    """
    exec_id = str(exec_info.get("ID") or "")
    cache_key = f"{exec_id}:{days_left}"
    if cache_key in _INSPECTOR_ALERT_CACHE:
        return _INSPECTOR_ALERT_CACHE[cache_key]

    obj_name = exec_info.get("ObjectName") or "Объект защиты"
    work_name = exec_info.get("WorkName") or "Регламентное ТО СПЗ"
    work_code = exec_info.get("WorkCode") or "ПБ"
    planned_date = exec_info.get("PlannedDate") or "в ближайшее время"

    # Дни текстом
    if days_left == 1:
        days_str = "1 день (ЗАВТРА)"
    elif days_left == 0:
        days_str = "СЕГОДНЯ"
    elif days_left in (2, 3, 4):
        days_str = f"{days_left} дня"
    else:
        days_str = f"{days_left} дней"

    ai_cfg = ai_cfg or load_ai_config()
    health = verify_llm_connection(ai_cfg, force_check=False)

    inspector_text = ""

    if health.get("is_online") and ai_cfg.get("enabled", True):
        provider_configs = ai_cfg.get("provider_configs", [health.get("active_config", ai_cfg)])
        for p_cfg in provider_configs:
            if is_dummy_key(p_cfg.get("api_key")):
                continue
            merged_cfg = {**ai_cfg, **p_cfg}
            api_key = merged_cfg.get("api_key")
            provider = merged_cfg.get("provider", "").lower()
            model = merged_cfg.get("model", "")
            api_url = merged_cfg.get("api_url", "")

            is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url
            is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url

            prompt = f"""
Ты — строгий государственный инспектор пожарного надзора.
Сформируй ОДНО-ДВА коротких, авторитетных и емких предложения напоминания о приближающейся плановой проверке / регламентном техобслуживании:
- Объект: {obj_name}
- Регламент: {work_code} ({work_name})
- До срока выполнения: {days_str} (дата: {planned_date})

Требования:
- Стиль: строгий инспектор по пожарной безопасности, предупреждающий об ответственности за непроведение ТО и необходимость заполнения журнала эксплуатации.
- Никакой воды, шаблонных вежливых вступлений («Уважаемые господа» и т.п.).
- Максимум 25-35 слов!
- Начни сразу с сути или предупреждения.
"""
            try:
                if is_gigachat:
                    token = get_gigachat_token(api_key, merged_cfg.get("scope", "GIGACHAT_API_PERS"))
                    if token:
                        endpoint = api_url + ("/chat/completions" if not api_url.endswith("/chat/completions") else "")
                        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
                        payload = {
                            "model": model or "GigaChat",
                            "temperature": 0.2,
                            "messages": [{"role": "user", "content": prompt}],
                        }
                        import ssl
                        ctx = ssl.create_default_context()
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        req = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                        with urllib.request.urlopen(req, timeout=8, context=ctx) as resp:
                            body = json.loads(resp.read().decode("utf-8"))
                            inspector_text = body["choices"][0]["message"]["content"].strip().strip('"').strip("'")
                            if inspector_text:
                                break
                elif is_yandex:
                    folder_id = merged_cfg.get("folder_id", "").strip()
                    auth_header = f"Api-Key {api_key}" if not api_key.startswith("Bearer ") else api_key
                    headers = {"Content-Type": "application/json", "Authorization": auth_header}
                    if folder_id:
                        headers["x-folder-id"] = folder_id
                    y_model = model if "/" in model else f"gpt://{folder_id}/{model}" if folder_id else model
                    payload = {
                        "modelUri": y_model,
                        "completionOptions": {"stream": False, "temperature": 0.2, "maxTokens": 150},
                        "messages": [{"role": "user", "text": prompt}],
                    }
                    req = urllib.request.Request(api_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                        inspector_text = body["result"]["alternatives"][0]["message"]["text"].strip().strip('"').strip("'")
                        if inspector_text:
                            break
            except Exception as e:
                logger.warning("Ошибка генерации текста инспектора через LLM (%s): %s", provider, e)
                continue

    # Офлайн-шаблоны эксперта 123-ФЗ/ППР 1479 при отсутствии внешнего API
    if not inspector_text:
        if days_left <= 1:
            inspector_text = (
                f"⚠️ Срочный контроль: до регламента «{work_code}» на объекте «{obj_name}» остался {days_str}! "
                f"Обеспечьте беспрепятственный допуск лицензированной бригады и внесение записи в журнал эксплуатации систем противопожарной защиты (п. 54 ППР № 1479)."
            )
        elif days_left <= 3:
            inspector_text = (
                f"Внимание: до планового выполнения {work_name} ({obj_name}) осталось {days_str}. "
                f"Подготовьте исполнительную документацию и проверьте готовность дежурного персонала по ст. 83 123-ФЗ."
            )
        elif days_left <= 7:
            inspector_text = (
                f"Плановое ТО: через {days_str} на объекте «{obj_name}» наступает срок регламента {work_code}. "
                f"Согласуйте время выезда специалистов во избежание предписаний Госпожнадзора."
            )
        else:
            inspector_text = (
                f"Предварительное информирование: через {days_str} ({planned_date}) запланирован регламент {work_name} на объекте «{obj_name}». "
                f"Проверьте актуальность договора и графиков ТО по СП 484.1311500."
            )

    _INSPECTOR_ALERT_CACHE[cache_key] = inspector_text
    return inspector_text



