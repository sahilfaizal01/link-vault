from __future__ import annotations

from datetime import datetime, timezone

import json

from . import database as db
from .ai import analyze_link
from .intelligence import compute_priority_score, find_similar_items, refine_bucket
from .metadata import fetch_page_metadata


async def process_item(item_id: int) -> dict | None:
    item = db.get_item(item_id)
    if not item:
        return None

    try:
        meta = await fetch_page_metadata(item["url"])
        analysis = await analyze_link(
            url=item["url"],
            title=meta.get("title") or item.get("title"),
            description=meta.get("description"),
            excerpt=meta.get("excerpt"),
            note=item.get("note"),
            source_type=meta.get("source_type") or "article",
        )
        bucket, bucket_kind = refine_bucket(analysis["bucket"], analysis["tags"])
        draft = {
            **item,
            "title": meta.get("title") or item.get("title"),
            "domain": meta.get("domain"),
            "summary": analysis["summary"],
            "tags": analysis["tags"],
            "bucket": bucket,
        }
        similar = find_similar_items(draft, db.list_all_for_similarity())
        priority = compute_priority_score(draft)
        return db.update_item(
            item_id,
            title=meta.get("title") or item.get("title"),
            domain=meta.get("domain"),
            source_type=meta.get("source_type"),
            summary=analysis["summary"],
            why_it_matters=analysis["why_it_matters"],
            bucket=bucket,
            bucket_kind=bucket_kind,
            tags=analysis["tags"],
            raw_excerpt=meta.get("excerpt"),
            priority_score=priority,
            similar_item_ids=json.dumps(similar),
            status="processed",
            error_message=None,
            processed_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        return db.update_item(
            item_id,
            status="failed",
            error_message=str(exc)[:500],
            processed_at=datetime.now(timezone.utc).isoformat(),
        )


async def process_pending(limit: int = 10) -> list[dict]:
    results: list[dict] = []
    for item in db.list_pending(limit=limit):
        processed = await process_item(item["id"])
        if processed:
            results.append(processed)
    return results
