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
    """Загрузка настроек ИИ из msg.cfg с поддержкой нескольких провайдеров"""
    cfg = configparser.ConfigParser()
    if MSG_CFG_PATH.exists():
        try:
            cfg.read(str(MSG_CFG_PATH), encoding="utf-8")
        except Exception as e:
            logger.error("Ошибка чтения msg.cfg: %s", e)
    
    section = cfg["ai_assistant"] if cfg.has_section("ai_assistant") else {}
    providers_str = section.get("providers", "").strip()
    if not providers_str:
        p = section.get("provider", "auto").strip().lower()
        providers_list = [p] if p else ["auto"]
    else:
        providers_list = [p.strip().lower() for p in providers_str.split(",") if p.strip()]

    # Собираем конфигурации для каждого поддерживаемого провайдера
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
                if not c["model"]: c["model"] = "GigaChat-Pro"
            elif p == "yandexgpt":
                c["api_url"] = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
                if not c["model"]: c["model"] = "yandexgpt/latest"
            elif p == "deepseek":
                c["api_url"] = "https://api.deepseek.com/v1"
                if not c["model"]: c["model"] = "deepseek-chat"
        provider_configs.append(c)

    # Дефолтная активная секция
    return {
        "enabled": section.getboolean("enabled", fallback=True),
        "provider": providers_list[0] if providers_list else "auto",
        "providers_chain": providers_list,
        "provider_configs": provider_configs,
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


def get_gigachat_token(auth_key: str, scope: str = "GIGACHAT_API_PERS") -> Optional[str]:
    """Получение и кэширование OAuth-токена Сбер GigaChat"""
    import time
    import ssl
    import uuid

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
        return "YaGPT"
    if p == "gigachat" or "gigachat" in m:
        return "GigaChat"
    if p == "deepseek" or "deepseek" in m:
        return "DeepSeek"
    if p == "proxyapi" or "proxyapi" in p:
        return "ProxyAPI"
    if p == "local_ollama" or "ollama" in p:
        return "Ollama"
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
    return "LLM"


def _ping_single_provider(p_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Пинг одного конкретного провайдера нейросети"""
    import ssl

    provider = p_cfg.get("provider", "auto").lower()
    api_key = p_cfg.get("api_key", "").strip()
    api_url = p_cfg.get("api_url", "").strip()
    model = p_cfg.get("model", "").strip()
    display_provider = get_provider_display_name(provider, model)

    if provider == "expert_rules" or not api_key:
        return {
            "status": "expert_offline",
            "is_online": False,
            "provider": provider,
            "display_name": "База 123-ФЗ (Без API)",
            "badge_text": "123-ФЗ",
            "badge_color": "amber",
            "description": "API-ключ не задан в msg.cfg. Работает экспертная нормативная база 123-ФЗ/СП.",
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
            "model": model or "deepseek-chat",
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

    import ssl
    provider = ai_cfg.get("provider", "auto").lower()
    model = ai_cfg.get("model", "deepseek-chat")
    api_url = ai_cfg.get("api_url", "https://api.openai.com/v1")

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
    is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url
    is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url

    ssl_ctx = None

    if is_gigachat:
        token = get_gigachat_token(api_key, ai_cfg.get("scope", "GIGACHAT_API_PERS"))
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
        folder_id = ai_cfg.get("folder_id", "").strip()
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
        folder_id = ai_cfg.get("folder_id", "").strip()
        if folder_id:
            headers["x-folder-id"] = folder_id

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
        timeout = ai_cfg.get("request_timeout_seconds", 15)
        urlopen_kwargs = {"timeout": timeout}
        if ssl_ctx:
            urlopen_kwargs["context"] = ssl_ctx

        with urllib.request.urlopen(req, **urlopen_kwargs) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            
            if is_yandex:
                # Ответ YandexGPT: result["result"]["alternatives"][0]["message"]["text"]
                content = result["result"]["alternatives"][0]["message"]["text"]
                cleaned = content.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("\n", 1)[-1]
                    if cleaned.endswith("```"):
                        cleaned = cleaned.rsplit("```", 1)[0]
                parsed = json.loads(cleaned)
            elif is_gigachat:
                # Ответ GigaChat: result["choices"][0]["message"]["content"]
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


def answer_assistant_question(question: str, context_page: str = "", ai_cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Интеллектуальный ИИ-консультант новичка:
    Отвечает на вопросы о логике работы программы 'Календарь ТО' и пожарной безопасности.
    Работает через LLM (если есть ключ) или через встроенную экспертную базу знаний.
    """
    q_lower = (question or "").lower().strip()
    ai_cfg = ai_cfg or load_ai_config()

    # Попытка вызова LLM (если онлайн)
    health = verify_llm_connection(ai_cfg, force_check=False)
    if health.get("is_online") and ai_cfg.get("enabled", True):
        active_p_cfg = health.get("active_config", ai_cfg)
        merged_cfg = {**ai_cfg, **active_p_cfg}
        api_key = merged_cfg.get("api_key")
        provider = merged_cfg.get("provider", "auto").lower()
        model = merged_cfg.get("model", "")
        api_url = merged_cfg.get("api_url", "")
        is_gigachat = provider == "gigachat" or "gigachat.devices.sberbank" in api_url
        is_yandex = provider == "yandexgpt" or "cloud.yandex" in api_url

        system_instruction = (
            "Ты — встроенный дружелюбный консультант программы «Календарь ТО» (учёт техобслуживания систем пожарной безопасности: АПС, СОУЭ, ВПВ, АУПТ, огнетушители по 123-ФЗ и СП).\n"
            "Твоя задача — максимально понятно, простыми словами объяснить новичку логику работы системы, куда нажать и что делать.\n"
            "Основные разделы:\n"
            "1. «Объекты» — карточки зданий, где задаются адрес, площадь, этажность, класс ФПО (Ф1.1-Ф5.3) и категория пожароопасности (А, Б, В, Г, Д).\n"
            "2. «Виды работ» — справочник регламентов ТО (шифры ПБ-01.XX - ПБ-10.XX).\n"
            "3. «Назначения» — привязка работы к объекту на период (например, на год) с выбором периодичности. Система сама рассчитывает даты!\n"
            "4. «Календарь» — интерактивная сетка дат со статусами (синий - план, зеленый - выполнено, красный - просрочено, желтый - перенос). В модалке дня можно закрыть всё в 1 клик.\n"
            "5. «Журнал» — журнал выполненных и запланированных работ с фильтрами и историей.\n"
            "6. «Счета» — выставление счетов и актов от разных юридических лиц с печатью А4.\n"
            "Отвечай кратко, структурированно, доброжелательно, используй списки и эмодзи."
        )

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
                        return {"ok": True, "answer": ans, "source": f"ИИ ({health.get('display_name', 'GigaChat')})"}
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
            logger.warning("Ошибка генерации ответа LLM консультанта: %s", e)

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
            "keys": ["ии", "нейросеть", "api", "gigachat", "yandex", "deepseek", "123-фз"],
            "answer": (
                "🤖 **Как работает ИИ в системе:**\n\n"
                "• **Онлайн-режим (зелёный индикатор)**: Если в `msg.cfg` указан ключ GigaChat, YandexGPT или DeepSeek, система использует нейросеть для интеллектуального аудита и анализа проектов.\n"
                "• **Автономный режим (янтарный индикатор)**: Если ключа нет, система работает на **встроенной экспертной нормативной базе 123-ФЗ, СП 484, СП 486 и ППР № 1479**, гарантируя 100% точность требований пожарной безопасности даже без интернета!"
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

