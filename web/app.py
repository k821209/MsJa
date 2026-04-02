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
from src.calendar import (
    get_today_events as _get_today,
    get_week_events as _get_week,
    get_upcoming_events as _get_upcoming,
    get_events_for_date as _get_events_date,
)
from src.documents import (
    get_document as _get_doc,
    get_document_stats as _get_doc_stats,
    get_document_versions as _get_doc_versions,
    list_documents as _list_docs,
    update_document as _update_doc,
    archive_document as _archive_doc,
)
from src.todos import (
    complete_todo as _complete_todo,
    create_todo as _create_todo,
    delete_todo as _delete_todo,
    get_todo as _get_todo,
    get_todo_stats as _get_todo_stats,
    list_todos as _list_todos,
    update_todo as _update_todo,
)
from src.dotenv import load_env, save_env_key, get_env_keys
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


@app.get("/page/calendar", response_class=HTMLResponse)
async def calendar_page(request: Request, date: str | None = None):
    from datetime import datetime
    conn = _conn()
    try:
        today = _get_today(conn)
        week = _get_week(conn)
        upcoming = _get_upcoming(conn, limit=15)
        selected_date = date or datetime.now().strftime("%Y-%m-%d")
        selected_events = _get_events_date(conn, selected_date) if date else today
        return templates.TemplateResponse(request=request, name="calendar.html", context={
            "request": request,
            "today_events": today,
            "week": week,
            "upcoming": upcoming,
            "selected_date": selected_date,
            "selected_events": selected_events,
        })
    finally:
        conn.close()


@app.get("/api/calendar/events")
async def api_calendar_events(date: str | None = None):
    conn = _conn()
    try:
        if date:
            return _get_events_date(conn, date)
        return _get_today(conn)
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
    dest = PROJECT_ROOT / "persona" / "avatar" / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    # Register in persona_images DB
    file_path = f"persona/avatar/{file.filename}"
    label = Path(file.filename).stem
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO persona_images (image_type, label, file_path, description) VALUES (?, ?, ?, ?)",
            ("uploaded", label, file_path, "Uploaded via web dashboard"),
        )
        conn.commit()
    finally:
        conn.close()
    return {"path": f"/persona/avatar/{file.filename}"}


@app.post("/api/avatar")
async def api_set_avatar(request: Request):
    body = await request.json()
    file_path = body.get("file_path")
    conn = _conn()
    try:
        conn.execute("UPDATE persona_meta SET avatar_path = ? WHERE id = 1", (file_path,))
        conn.commit()
        return {"status": "ok", "avatar_path": file_path}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.delete("/api/images/{image_id}")
async def api_delete_image(image_id: int):
    conn = _conn()
    try:
        # Get image info before deleting
        row = conn.execute("SELECT file_path FROM persona_images WHERE id = ?", (image_id,)).fetchone()
        if row is None:
            return JSONResponse({"error": "Image not found"}, status_code=404)

        file_path = PROJECT_ROOT / row["file_path"]

        # Check if this is the current avatar
        meta = conn.execute("SELECT avatar_path FROM persona_meta WHERE id = 1").fetchone()
        if meta and meta["avatar_path"] == row["file_path"]:
            conn.execute("UPDATE persona_meta SET avatar_path = 'persona/avatar/default.png' WHERE id = 1")

        # Delete from DB
        conn.execute("DELETE FROM persona_images WHERE id = ?", (image_id,))
        conn.commit()

        # Delete file
        if file_path.exists():
            file_path.unlink()

        return {"status": "deleted", "image_id": image_id}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


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


# ── Todos ─────────────────────────────────────────────────────


@app.get("/page/todos", response_class=HTMLResponse)
async def todos_page(
    request: Request,
    status: str | None = None,
    priority: str | None = None,
    tag: str | None = None,
    q: str | None = None,
):
    conn = _conn()
    try:
        tags = [t.strip() for t in tag.split(",")] if tag else None
        include_done = status in ("done", "cancelled")
        todos = _list_todos(conn, status=status, priority=priority, tags=tags,
                            query=q, include_done=include_done, limit=50)
        stats = _get_todo_stats(conn)
        return templates.TemplateResponse(request=request, name="todos.html", context={
            "request": request,
            "todos": todos,
            "stats": stats,
            "filters": {"status": status, "priority": priority, "tag": tag, "q": q},
        })
    finally:
        conn.close()


@app.post("/api/todos")
async def api_create_todo(request: Request):
    body = await request.json()
    conn = _conn()
    try:
        tags = [t.strip() for t in body.get("tags", "").split(",")] if body.get("tags") else None
        todo_id = _create_todo(
            conn, title=body["title"], description=body.get("description"),
            priority=body.get("priority", "medium"), due_date=body.get("due_date"),
            calendar_event_id=body.get("calendar_event_id"), tags=tags,
        )
        return {"todo_id": todo_id}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.put("/api/todos/{todo_id}")
async def api_update_todo(todo_id: int, request: Request):
    body = await request.json()
    conn = _conn()
    try:
        tags = [t.strip() for t in body["tags"].split(",")] if "tags" in body else None
        result = _update_todo(
            conn, todo_id, title=body.get("title"), description=body.get("description"),
            priority=body.get("priority"), status=body.get("status"),
            due_date=body.get("due_date"), tags=tags,
        )
        return result
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.post("/api/todos/{todo_id}/complete")
async def api_complete_todo(todo_id: int):
    conn = _conn()
    try:
        return _complete_todo(conn, todo_id)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


@app.delete("/api/todos/{todo_id}")
async def api_delete_todo(todo_id: int):
    conn = _conn()
    try:
        _delete_todo(conn, todo_id)
        return {"status": "deleted"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    finally:
        conn.close()


# ── Settings ──────────────────────────────────────────────────


# Keys that the settings page manages
MANAGED_KEYS = ["GEMINI_API_KEY"]


@app.get("/page/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    env = load_env()
    keys = {k: env.get(k, "") for k in MANAGED_KEYS}
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "request": request,
        "keys": keys,
    })


@app.post("/api/settings/keys")
async def api_save_keys(request: Request):
    body = await request.json()
    try:
        for key, value in body.items():
            if key in MANAGED_KEYS:
                save_env_key(key, value)
        return {"status": "ok"}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.get("/api/settings/keys")
async def api_get_keys():
    env = load_env()
    # Mask values for display (show first 8 chars + ***)
    masked = {}
    for k in MANAGED_KEYS:
        v = env.get(k, "")
        masked[k] = v[:8] + "***" if len(v) > 8 else v
    return masked


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
        """Read from PTY and send to WebSocket with buffering.

        Collects output over a short window and sends in one batch
        to avoid the flickering redraw effect with TUI apps like Claude Code.
        """
        try:
            while True:
                # Wait for data to be available
                await asyncio.sleep(0.005)
                buf = bytearray()
                try:
                    # Drain all available data
                    while True:
                        chunk = os.read(master_fd, 16384)
                        if chunk:
                            buf.extend(chunk)
                        else:
                            break
                except (OSError, BlockingIOError):
                    pass

                if buf:
                    # Small delay to collect more data from burst writes
                    await asyncio.sleep(0.015)
                    try:
                        while True:
                            chunk = os.read(master_fd, 16384)
                            if chunk:
                                buf.extend(chunk)
                            else:
                                break
                    except (OSError, BlockingIOError):
                        pass

                    await websocket.send_bytes(buf)
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
