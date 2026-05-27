from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from . import database as db
from .ai import build_digest
from .config import CANONICAL_BUCKETS, HOST, PORT
from .database import init_db
from .import_service import import_google_chat_text, import_paste_text, import_whatsapp_text
from .processor import process_item, process_pending

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"

app = FastAPI(title="Link Vault", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SaveItemRequest(BaseModel):
    url: HttpUrl
    title: str | None = None
    note: str | None = Field(default=None, max_length=2000)


class UpdateItemRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    bucket: str | None = Field(default=None, max_length=120)


class PasteImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5_000_000)
    source: str = Field(default="paste", max_length=64)
    process: bool = True


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/features")
def features() -> dict[str, Any]:
    from .ai import _build_client

    return {
        "mvp": True,
        "ai_grouping": {
            "strategy": "hybrid",
            "canonical_buckets": CANONICAL_BUCKETS,
            "llm_enabled": _build_client() is not None,
            "embeddings": False,
            "emerging_buckets": True,
        },
        "quality_intelligence": {
            "url_dedupe": True,
            "priority_scoring": True,
            "similar_links_heuristic": True,
            "embedding_similarity": False,
        },
        "workflow": {
            "chrome_extension": True,
            "web_dashboard": True,
            "whatsapp_import": "export_txt",
            "google_chat_import": "takeout_json_or_paste",
            "live_whatsapp_api": False,
            "live_google_chat_api": False,
            "email_digest": False,
        },
    }


@app.post("/api/items")
async def create_item(payload: SaveItemRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    url = str(payload.url)
    domain = urlparse(url).netloc.replace("www.", "")
    item, _created = db.insert_item(
        url,
        title=payload.title,
        note=payload.note,
        domain=domain,
        import_source="extension",
    )
    background_tasks.add_task(process_item, item["id"])
    return item


@app.get("/api/items")
def get_items(
    bucket: str | None = None,
    status: str | None = None,
    search: str | None = None,
    import_source: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    return db.list_items(
        bucket=bucket,
        status=status,
        search=search,
        import_source=import_source,
        limit=limit,
    )


@app.post("/api/import/whatsapp")
async def import_whatsapp(
    file: UploadFile = File(...),
    process: bool = True,
) -> dict[str, Any]:
    raw = await file.read()
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            content = None
    if content is None:
        raise HTTPException(status_code=400, detail="Could not decode file")
    result = await import_whatsapp_text(content, process=process)
    if result["found_urls"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No URLs found. Export chat as .txt (Without media) and try again.",
        )
    return result


@app.post("/api/import/google-chat")
async def import_google_chat(
    file: UploadFile = File(...),
    process: bool = True,
) -> dict[str, Any]:
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1", errors="replace")
    result = await import_google_chat_text(content, process=process)
    if result["found_urls"] == 0:
        raise HTTPException(
            status_code=400,
            detail="No URLs found in export. Use Google Takeout (Chat) JSON or paste messages.",
        )
    return result


@app.post("/api/import/paste")
async def import_paste(payload: PasteImportRequest) -> dict[str, Any]:
    result = await import_paste_text(
        payload.text,
        source=payload.source,
        process=payload.process,
    )
    if result["found_urls"] == 0:
        raise HTTPException(status_code=400, detail="No URLs found in pasted text")
    return result


@app.get("/api/items/{item_id}")
def get_item(item_id: int) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.patch("/api/items/{item_id}")
def patch_item(item_id: int, payload: UpdateItemRequest) -> dict[str, Any]:
    fields = payload.model_dump(exclude_unset=True)
    item = db.update_item(item_id, **fields)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/api/items/{item_id}/reprocess")
async def reprocess_item(item_id: int) -> dict[str, Any]:
    item = db.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.update_item(item_id, status="pending", error_message=None)
    processed = await process_item(item_id)
    return processed or item


@app.post("/api/process-pending")
async def process_pending_endpoint(limit: int = 20) -> dict[str, Any]:
    processed = await process_pending(limit=limit)
    return {"processed_count": len(processed), "items": processed}


@app.post("/api/reclassify-all")
async def reclassify_all(limit: int = 500) -> dict[str, Any]:
    """Re-run bucketing/summaries for all saved links (uses new bucket taxonomy)."""
    with db.connect() as conn:
        conn.execute(
            """
            UPDATE items
            SET status = 'pending',
                bucket = NULL,
                bucket_kind = NULL,
                summary = NULL,
                why_it_matters = NULL,
                tags = NULL,
                similar_item_ids = NULL,
                priority_score = NULL,
                processed_at = NULL,
                error_message = NULL
            """
        )
    processed = await process_pending(limit=limit)
    return {"reclassified": len(processed), "items": processed[:20]}


@app.get("/api/buckets")
def get_buckets() -> list[dict[str, Any]]:
    return db.bucket_summary()


@app.get("/api/digest")
async def get_digest(days: int = 14) -> dict[str, Any]:
    items = db.list_items(status="processed", limit=500)
    if days > 0:
        # Filter is best-effort on ISO timestamps
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        filtered = []
        for item in items:
            saved = item.get("saved_at")
            if not saved:
                continue
            try:
                if datetime.fromisoformat(saved) >= cutoff:
                    filtered.append(item)
            except ValueError:
                filtered.append(item)
        items = filtered or items
    return await build_digest(items)


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int) -> dict[str, str]:
    with db.connect() as conn:
        cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"status": "deleted"}


if WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")


def run() -> None:
    import uvicorn

    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=False)


if __name__ == "__main__":
    run()
