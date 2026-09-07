# -*- coding: utf-8 -*-
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db.session import engine
from app.db.base import Base
from app.routers import objects, works, assignments, executions, dashboard, invoices, settings, ai

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


app.include_router(objects.router, prefix="/api/objects", tags=["objects"])
app.include_router(works.router, prefix="/api/works", tags=["works"])
app.include_router(assignments.router, prefix="/api/assignments", tags=["assignments"])
app.include_router(executions.router, prefix="/api/executions", tags=["executions"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "app": "Календарь ТО Calendar", "version": "1.0.0"}
