from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from . import database as db
from .importers import ExtractedLink, parse_google_chat_export, parse_paste, parse_whatsapp_export
from .processor import process_item


async def import_links(
    links: list[ExtractedLink],
    *,
    import_source: str,
    process: bool = True,
) -> dict[str, Any]:
    created = 0
    updated = 0
    item_ids: list[int] = []

    for link in links:
        domain = urlparse(link.url).netloc.replace("www.", "")
        note_parts = [p for p in (link.note, link.sender and f"from {link.sender}") if p]
        note = " · ".join(note_parts) if note_parts else None
        if link.seen_at and note:
            note = f"{note} ({link.seen_at})"
        elif link.seen_at:
            note = link.seen_at

        item, is_new = db.insert_item(
            link.url,
            note=note,
            domain=domain,
            import_source=import_source,
            message_context=link.context,
        )
        item_ids.append(item["id"])
        if is_new:
            created += 1
        else:
            updated += 1

    processed_count = 0
    if process:
        for item_id in item_ids:
            result = await process_item(item_id)
            if result and result.get("status") == "processed":
                processed_count += 1

    return {
        "import_source": import_source,
        "found_urls": len(links),
        "created": created,
        "updated": updated,
        "skipped_duplicates": updated,
        "processed": processed_count,
        "item_ids": item_ids,
    }


async def import_whatsapp_text(content: str, *, process: bool = True) -> dict[str, Any]:
    links = parse_whatsapp_export(content)
    return await import_links(links, import_source="whatsapp", process=process)


async def import_google_chat_text(content: str, *, process: bool = True) -> dict[str, Any]:
    links = parse_google_chat_export(content)
    return await import_links(links, import_source="google_chat", process=process)


async def import_paste_text(content: str, source: str = "paste", *, process: bool = True) -> dict[str, Any]:
    links = parse_paste(content, source=source)
    return await import_links(links, import_source=source, process=process)
