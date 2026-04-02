"""Deevo companion web UI — visual dashboard for persona, images, documents."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Ensure project root importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import init_db
from src.memory import get_memory_stats as _get_memory_stats, query_memories as _query_memories
from src.persona import (
    get_active_images,
    get_active_lore,
    get_active_rules,
    get_avatar,
    get_current_traits,
    get_lore_history,
    get_persona_state,
    get_trait_definitions,
    get_trait_history,
)
from src.signals import get_signal_summary
from src.reflection import get_reflection_history

app = FastAPI(title="Deevo Dashboard")

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
# Serve persona images from project root
app.mount("/persona", StaticFiles(directory=str(PROJECT_ROOT / "persona")), name="persona")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _conn():
    return init_db()


# ── Pages ──────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    conn = _conn()
    try:
        state = get_persona_state(conn)
        trait_defs = {d["trait_key"]: d for d in get_trait_definitions(conn)}
        signals = get_signal_summary(conn)
        reflections = get_reflection_history(conn, limit=5)
        memory_stats = _get_memory_stats(conn)
        return templates.TemplateResponse(request=request, name="dashboard.html", context={
            "request": request,
            "state": state,
            "trait_defs": trait_defs,
            "signals": signals,
            "reflections": reflections,
            "memory_stats": memory_stats,
        })
    finally:
        conn.close()


@app.get("/lore", response_class=HTMLResponse)
async def lore_page(request: Request):
    conn = _conn()
    try:
        lore = get_active_lore(conn, limit=50)
        return templates.TemplateResponse(request=request, name="lore.html", context={
            "request": request,
            "lore": lore,
        })
    finally:
        conn.close()


@app.get("/images", response_class=HTMLResponse)
async def images_page(request: Request):
    conn = _conn()
    try:
        images = get_active_images(conn)
        avatar = get_avatar(conn)
        return templates.TemplateResponse(request=request, name="images.html", context={
            "request": request,
            "images": images,
            "avatar": avatar,
        })
    finally:
        conn.close()


@app.get("/memories", response_class=HTMLResponse)
async def memories_page(request: Request, type: str | None = None, tag: str | None = None, q: str | None = None):
    conn = _conn()
    try:
        tags = [t.strip() for t in tag.split(",")] if tag else None
        memories = _query_memories(conn, memory_type=type, tags=tags, query=q, limit=50)
        stats = _get_memory_stats(conn)
        return templates.TemplateResponse(request=request, name="memories.html", context={
            "request": request,
            "memories": memories,
            "stats": stats,
            "filters": {"type": type, "tag": tag, "q": q},
        })
    finally:
        conn.close()


@app.get("/reflections", response_class=HTMLResponse)
async def reflections_page(request: Request):
    conn = _conn()
    try:
        reflections = get_reflection_history(conn, limit=20)
        return templates.TemplateResponse(request=request, name="reflections.html", context={
            "request": request,
            "reflections": reflections,
        })
    finally:
        conn.close()


# ── API endpoints ──────────────────────────────────────────────


@app.get("/api/state")
async def api_state():
    conn = _conn()
    try:
        return get_persona_state(conn)
    finally:
        conn.close()


@app.get("/api/trait/{trait_key}/history")
async def api_trait_history(trait_key: str, limit: int = 20):
    conn = _conn()
    try:
        return get_trait_history(conn, trait_key=trait_key, limit=limit)
    finally:
        conn.close()


@app.get("/api/lore/{lore_id}/history")
async def api_lore_history(lore_id: int):
    conn = _conn()
    try:
        return get_lore_history(conn, lore_id=lore_id)
    finally:
        conn.close()


@app.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    dest = UPLOADS_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": f"/static/uploads/{file.filename}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3000)
