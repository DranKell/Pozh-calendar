# -*- coding: utf-8 -*-
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.session import engine
from app.db.base import Base
from app.routers import objects, works, assignments, executions, dashboard, invoices, settings, ai, companies

Base.metadata.create_all(bind=engine)

STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Календарь ТО Calendar", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# NO_CACHE_MIDDLEWARE
@app.middleware("http")
async def _no_cache_static(request, call_next):
    response = await call_next(request)
    p = request.url.path
    if p == "/" or p.startswith("/static") or p.endswith(".css") or p.endswith(".js") or p.endswith(".html"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.on_event("startup")
async def startup_notifier_worker():
    """
    Запуск фонового планировщика для ежедневной рассылки напоминаний ТО.
    """
    import asyncio
    import logging
    from datetime import datetime, date
    from app.db.session import SessionLocal
    from app.services.notifier import (
        load_notifier_config,
        check_and_send_scheduled_reminders,
        broadcast_notification,
    )

    logger = logging.getLogger("notifier_worker")

    async def _scheduler_loop():
        # Небольшая пауза при запуске сервиса
        await asyncio.sleep(5)
        cfg = load_notifier_config()

        # Тестовый пинг при старте, если включен в msg.cfg
        if cfg["general"].get("send_startup_ping"):
            try:
                broadcast_notification(
                    subject="Служба оповещений запущена",
                    message_text="✅ Сервис «Календарь ТО» успешно запущен и готов к рассылке уведомлений."
                )
            except Exception as e:
                logger.error("Ошибка отправки startup-ping: %s", e)

        last_checked_date: Optional[date] = None

        while True:
            try:
                now = datetime.now()
                today = now.date()
                cfg = load_notifier_config()
                target_time_str = cfg["triggers"].get("daily_digest_time", "08:30")
                try:
                    th, tm = map(int, target_time_str.split(":"))
                except Exception:
                    th, tm = 8, 30

                # Если наступило или прошло время рассылки, и сегодня еще не проверяли
                if (now.hour > th or (now.hour == th and now.minute >= tm)) and last_checked_date != today:
                    logger.info("Запуск плановой рассылки напоминаний за %s", today)
                    check_and_send_scheduled_reminders(SessionLocal)
                    last_checked_date = today

            except Exception as exc:
                logger.error("Ошибка в цикле фонового планировщика: %s", exc)

            # Проверка каждые 60 секунд
            await asyncio.sleep(60)

    asyncio.create_task(_scheduler_loop())



app.include_router(objects.router, prefix="/api/objects", tags=["objects"])
app.include_router(works.router, prefix="/api/works", tags=["works"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["assignments"])
app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "app": "Календарь ТО Calendar", "version": "1.0.0"}
