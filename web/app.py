"""Deevo companion web UI — visual dashboard for persona, images, documents, terminal."""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import pty
import select
import shutil
import struct
import sys
import termios
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Ensure project root importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.db import init_db
from src.memory import (
    add_memory as _add_mem,
    archive_memory as _archive_mem,
    delete_memory as _delete_mem,
    get_memory as _get_mem,
    get_memory_stats as _get_memory_stats,
    query_memories as _query_memories,
)
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
from src.documents import (
    get_document as _get_doc,
    get_document_stats as _get_doc_stats,
    get_document_versions as _get_doc_versions,
    list_documents as _list_docs,
    update_document as _update_doc,
    archive_document as _archive_doc,
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


# ── Shell (outer frame) ────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def shell(request: Request):
    return templates.TemplateResponse(request=request, name="shell.html", context={
        "request": request,
    })


# ── Pages (served inside iframe via /page/ prefix) ─────────────


@app.get("/page/", response_class=HTMLResponse)
@app.get("/page", response_class=HTMLResponse)
async def page_dashboard(request: Request):
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


@app.get("/page/lore", response_class=HTMLResponse)
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


@app.get("/page/images", response_class=HTMLResponse)
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


@app.get("/page/memories", response_class=HTMLResponse)
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


@app.get("/page/reflections", response_class=HTMLResponse)
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


# ── Memory CRUD API ────────────────────────────────────────────


@app.post("/api/memories")
async def api_create_memory(request: Request):
    body = await request.json()
    conn = _conn()
    try:
        tags = None
        if body.get("tags"):
            tags = [t.strip() for t in body["tags"].split(",") if t.strip()]
        mem_id = _add_mem(
            conn,
            memory_type=body["memory_type"],
            content=body["content"],
            importance=body.get("importance", 0.5),
            tags=tags,
        )
        return {"memory_id": mem_id}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.put("/api/memories/{mem_id}")
async def api_update_memory(mem_id: int, request: Request):
    body = await request.json()
    conn = _conn()
    try:
        # Update content
        if "content" in body:
            conn.execute(
                "UPDATE memories SET content = ? WHERE id = ?",
                (body["content"], mem_id),
            )
        # Update importance
        if "importance" in body:
            conn.execute(
                "UPDATE memories SET importance = ? WHERE id = ?",
                (body["importance"], mem_id),
            )
        # Update tags
        if "tags" in body:
            conn.execute("DELETE FROM memory_tags WHERE memory_id = ?", (mem_id,))
            if body["tags"]:
                for tag in [t.strip() for t in body["tags"].split(",") if t.strip()]:
                    conn.execute(
                        "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                        (mem_id, tag),
                    )
        conn.commit()
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.post("/api/memories/{mem_id}/archive")
async def api_archive_memory(mem_id: int):
    conn = _conn()
    try:
        _archive_mem(conn, mem_id)
        return {"status": "archived"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.delete("/api/memories/{mem_id}")
async def api_delete_memory(mem_id: int):
    conn = _conn()
    try:
        _delete_mem(conn, mem_id)
        return {"status": "deleted"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.post("/api/upload/image")
async def upload_image(file: UploadFile = File(...)):
    dest = UPLOADS_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": f"/static/uploads/{file.filename}"}


# ── Documents ──────────────────────────────────────────────────


@app.get("/page/documents", response_class=HTMLResponse)
async def documents_page(
    request: Request,
    type: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    q: str | None = None,
):
    conn = _conn()
    try:
        tags = [t.strip() for t in tag.split(",")] if tag else None
        docs = _list_docs(conn, doc_type=type, status=status, tags=tags, query=q, limit=50)
        stats = _get_doc_stats(conn)
        return templates.TemplateResponse(request=request, name="documents.html", context={
            "request": request,
            "documents": docs,
            "stats": stats,
            "filters": {"type": type, "status": status, "tag": tag, "q": q},
        })
    finally:
        conn.close()


@app.get("/page/documents/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: int):
    conn = _conn()
    try:
        doc = _get_doc(conn, doc_id)
        if doc is None:
            return HTMLResponse("<h1>Document not found</h1>", status_code=404)
        versions = _get_doc_versions(conn, doc_id)
        return templates.TemplateResponse(request=request, name="document_detail.html", context={
            "request": request,
            "doc": doc,
            "versions": versions,
        })
    finally:
        conn.close()


@app.post("/api/documents/{doc_id}/status")
async def api_update_doc_status(doc_id: int, request: Request):
    body = await request.json()
    new_status = body.get("status")
    conn = _conn()
    try:
        if new_status == "archived":
            _archive_doc(conn, doc_id)
        else:
            _update_doc(conn, doc_id, status=new_status, edited_by="user", change_summary=f"Status → {new_status}")
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.get("/api/documents/{doc_id}/versions")
async def api_doc_versions(doc_id: int):
    conn = _conn()
    try:
        return _get_doc_versions(conn, doc_id)
    finally:
        conn.close()


# ── WebSocket Terminal (PTY) ───────────────────────────────────


def _set_pty_size(fd: int, cols: int, rows: int) -> None:
    """Set the PTY window size."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


@app.websocket("/ws/terminal")
async def ws_terminal(websocket: WebSocket):
    await websocket.accept()

    # Spawn shell with PTY
    master_fd, slave_fd = pty.openpty()

    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"

    pid = os.fork()
    if pid == 0:
        # Child — become the shell
        os.close(master_fd)
        os.setsid()
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        os.close(slave_fd)
        shell = os.environ.get("SHELL", "/bin/zsh")
        os.chdir(str(PROJECT_ROOT))
        os.execvpe(shell, [shell, "-l"], env)

    # Parent — relay between WebSocket and PTY
    os.close(slave_fd)

    # Make master_fd non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    async def read_pty():
        """Read from PTY and send to WebSocket."""
        loop = asyncio.get_event_loop()
        try:
            while True:
                await asyncio.sleep(0.01)
                try:
                    data = os.read(master_fd, 4096)
                    if data:
                        await websocket.send_text(data.decode("utf-8", errors="replace"))
                except OSError:
                    await asyncio.sleep(0.05)
                except BlockingIOError:
                    pass
        except Exception:
            pass

    reader_task = asyncio.create_task(read_pty())

    try:
        while True:
            msg = await websocket.receive_text()
            payload = json.loads(msg)

            if payload["type"] == "input":
                os.write(master_fd, payload["data"].encode("utf-8"))
            elif payload["type"] == "resize":
                _set_pty_size(master_fd, payload["cols"], payload["rows"])
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        reader_task.cancel()
        os.close(master_fd)
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3000)
