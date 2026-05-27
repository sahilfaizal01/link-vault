from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import DB_PATH


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(db_path: Path | None = None) -> None:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                domain TEXT,
                source_type TEXT,
                note TEXT,
                summary TEXT,
                why_it_matters TEXT,
                bucket TEXT,
                tags TEXT,
                raw_excerpt TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                error_message TEXT,
                saved_at TEXT NOT NULL,
                processed_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_items_bucket ON items(bucket);
            CREATE INDEX IF NOT EXISTS idx_items_status ON items(status);
            CREATE INDEX IF NOT EXISTS idx_items_saved_at ON items(saved_at);
            """
        )
        _migrate(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(items)").fetchall()}
    additions = {
        "import_source": "TEXT",
        "message_context": "TEXT",
        "priority_score": "REAL",
        "bucket_kind": "TEXT",
        "similar_item_ids": "TEXT",
    }
    for name, col_type in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE items ADD COLUMN {name} {col_type}")


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    tags = data.get("tags")
    if tags:
        try:
            data["tags"] = json.loads(tags)
        except json.JSONDecodeError:
            data["tags"] = []
    else:
        data["tags"] = []
    return data


def insert_item(
    url: str,
    *,
    title: str | None = None,
    note: str | None = None,
    domain: str | None = None,
    import_source: str | None = None,
    message_context: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Returns (item, created) where created is False if URL already existed."""
    now = _utc_now()
    with connect() as conn:
        existing = conn.execute("SELECT id FROM items WHERE url = ?", (url,)).fetchone()
        conn.execute(
            """
            INSERT INTO items (
                url, title, domain, note, import_source, message_context,
                status, saved_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(url) DO UPDATE SET
                note = COALESCE(excluded.note, items.note),
                title = COALESCE(excluded.title, items.title),
                import_source = COALESCE(excluded.import_source, items.import_source),
                message_context = COALESCE(excluded.message_context, items.message_context),
                status = CASE
                    WHEN items.status = 'processed' THEN items.status
                    ELSE 'pending'
                END
            """,
            (url, title, domain, note, import_source, message_context, now),
        )
        row = conn.execute("SELECT * FROM items WHERE url = ?", (url,)).fetchone()
    return row_to_dict(row), existing is None  # type: ignore[return-value]


def update_item(item_id: int, **fields: Any) -> dict[str, Any] | None:
    if not fields:
        return get_item(item_id)
    if "tags" in fields and isinstance(fields["tags"], list):
        fields["tags"] = json.dumps(fields["tags"])
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [item_id]
    with connect() as conn:
        conn.execute(f"UPDATE items SET {columns} WHERE id = ?", values)
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_dict(row)


def get_item(item_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return row_to_dict(row)


def list_items(
    *,
    bucket: str | None = None,
    status: str | None = None,
    search: str | None = None,
    import_source: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    query = "SELECT * FROM items WHERE 1=1"
    params: list[Any] = []
    if bucket:
        query += " AND bucket = ?"
        params.append(bucket)
    if status:
        query += " AND status = ?"
        params.append(status)
    if import_source:
        query += " AND import_source = ?"
        params.append(import_source)
    if search:
        query += " AND (title LIKE ? OR url LIKE ? OR summary LIKE ? OR note LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like, like, like])
    query += " ORDER BY saved_at DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def list_pending(limit: int = 20) -> list[dict[str, Any]]:
    return list_items(status="pending", limit=limit)


def bucket_summary() -> list[dict[str, Any]]:
    from .buckets import CANONICAL_BUCKETS

    order_cases = " ".join(
        f"WHEN COALESCE(bucket, 'Unsorted') = '{name.replace(chr(39), '')}' THEN {i}"
        for i, name in enumerate(CANONICAL_BUCKETS)
    )
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT
                COALESCE(bucket, 'Unsorted') AS bucket,
                COUNT(*) AS count,
                MAX(saved_at) AS latest_saved_at
            FROM items
            WHERE status IN ('processed', 'pending')
            GROUP BY COALESCE(bucket, 'Unsorted')
            ORDER BY
                CASE {order_cases} ELSE 999 END,
                count DESC,
                bucket ASC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def list_all_for_similarity(limit: int = 1000) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM items ORDER BY saved_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [row_to_dict(r) for r in rows]  # type: ignore[misc]


def mark_reprocess_all() -> int:
    with connect() as conn:
        cur = conn.execute(
            """
            UPDATE items
            SET status = 'pending', processed_at = NULL, error_message = NULL
            """
        )
    return cur.rowcount
