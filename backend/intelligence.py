from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .buckets import CANONICAL_BUCKETS, DEFAULT_BUCKET


def normalize_url_key(url: str) -> str:
    parsed = urlparse(url.lower().strip())
    path = parsed.path.rstrip("/")
    return f"{parsed.netloc.replace('www.', '')}{path}"


def compute_priority_score(item: dict[str, Any]) -> float:
    """Lightweight priority: recency + source + richness of metadata."""
    score = 50.0
    source = (item.get("import_source") or "").lower()
    if source in ("whatsapp", "google_chat"):
        score += 10.0
    if item.get("note"):
        score += 8.0
    if item.get("summary"):
        score += 5.0
    if (item.get("domain") or "").find("linkedin.com") >= 0:
        score += 7.0
    tags = item.get("tags") or []
    score += min(len(tags) * 2.0, 10.0)
    status = item.get("status")
    if status == "pending":
        score += 3.0
    return round(min(score, 100.0), 1)


def find_similar_items(item: dict[str, Any], all_items: list[dict[str, Any]]) -> list[int]:
    """Same-domain + overlapping title tokens (no embeddings in MVP)."""
    key = normalize_url_key(item.get("url") or "")
    title_tokens = set(re.findall(r"[a-z0-9]{4,}", (item.get("title") or "").lower()))
    similar: list[int] = []
    for other in all_items:
        if other["id"] == item["id"]:
            continue
        if normalize_url_key(other.get("url") or "") == key:
            similar.append(other["id"])
            continue
        other_tokens = set(re.findall(r"[a-z0-9]{4,}", (other.get("title") or "").lower()))
        if title_tokens and other_tokens:
            overlap = len(title_tokens & other_tokens) / max(len(title_tokens), 1)
            if overlap >= 0.5 and item.get("domain") == other.get("domain"):
                similar.append(other["id"])
    return similar[:5]


def refine_bucket(bucket: str | None, tags: list[str]) -> tuple[str, str]:
    """
    Hybrid grouping: canonical bucket + emerging label when tags don't fit well.
    Returns (bucket, bucket_kind) where bucket_kind is 'canonical' or 'emerging'.
    """
    if bucket and bucket in CANONICAL_BUCKETS:
        return bucket, "canonical"
    if bucket and bucket not in CANONICAL_BUCKETS:
        return f"Emerging: {bucket[:40]}", "emerging"
    if tags:
        label = tags[0].replace("-", " ").title()[:40]
        return f"Emerging: {label}", "emerging"
    return bucket or DEFAULT_BUCKET, "canonical"
