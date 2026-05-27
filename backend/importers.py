from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

# http(s) URLs; skips obvious media-only paths
URL_PATTERN = re.compile(
    r"https?://[^\s<>\"')\]]+",
    re.IGNORECASE,
)

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
}

WHATSAPP_LINE = re.compile(
    r"^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?)\]\s*(.+?):\s*(.+)$",
    re.IGNORECASE,
)


@dataclass
class ExtractedLink:
    url: str
    note: str | None = None
    context: str | None = None
    sender: str | None = None
    seen_at: str | None = None


def normalize_url(url: str) -> str:
    url = url.rstrip(".,);]>'\"")
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url
    query = parse_qs(parsed.query, keep_blank_values=True)
    filtered = [
        f"{k}={query[k][0]}"
        for k in sorted(query)
        if k.lower() not in TRACKING_PARAMS and query[k]
    ]
    clean = parsed._replace(query="&".join(filtered), fragment="")
    return urlunparse(clean)


def _is_useful_url(url: str) -> bool:
    lower = url.lower()
    if any(
        skip in lower
        for skip in (
            "whatsapp.com",
            "chat.google.com",
            "accounts.google.com",
            "google.com/url?",
            "giphy.com",
            "tenor.com",
        )
    ):
        return False
    if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".pdf")):
        return False
    return True


def extract_urls_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in URL_PATTERN.finditer(text):
        normalized = normalize_url(match.group(0))
        if normalized not in seen and _is_useful_url(normalized):
            seen.add(normalized)
            urls.append(normalized)
    return urls


def parse_whatsapp_export(content: str) -> list[ExtractedLink]:
    results: list[ExtractedLink] = []
    seen: set[str] = set()

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        sender = None
        body = line
        seen_at = None

        match = WHATSAPP_LINE.match(line)
        if match:
            date_part, time_part, sender, body = match.groups()
            seen_at = f"{date_part} {time_part}".strip()

        for url in extract_urls_from_text(body):
            if url in seen:
                continue
            seen.add(url)
            note = body.replace(url, "").strip() or None
            if note and len(note) > 240:
                note = note[:237] + "..."
            results.append(
                ExtractedLink(
                    url=url,
                    note=note,
                    context=line[:400] if len(line) > len(url) else None,
                    sender=sender,
                    seen_at=seen_at,
                )
            )

    # Fallback: plain dump without timestamp lines
    if not results:
        for url in extract_urls_from_text(content):
            if url not in seen:
                seen.add(url)
                results.append(ExtractedLink(url=url, context="whatsapp-export"))
    return results


def _walk_json_for_text(node: Any, texts: list[str]) -> None:
    if isinstance(node, str):
        if "http://" in node or "https://" in node:
            texts.append(node)
    elif isinstance(node, dict):
        for key in ("text", "message", "content", "body", "snippet", "argumentText"):
            if key in node and isinstance(node[key], str):
                texts.append(node[key])
        for value in node.values():
            _walk_json_for_text(value, texts)
    elif isinstance(node, list):
        for item in node:
            _walk_json_for_text(item, texts)


def parse_google_chat_export(content: str) -> list[ExtractedLink]:
    results: list[ExtractedLink] = []
    seen: set[str] = set()

    try:
        data = json.loads(content)
        texts: list[str] = []
        _walk_json_for_text(data, texts)
        blob = "\n".join(texts)
    except json.JSONDecodeError:
        blob = content

    for url in extract_urls_from_text(blob):
        if url in seen:
            continue
        seen.add(url)
        results.append(
            ExtractedLink(
                url=url,
                note="Imported from Google Chat export",
                context="google-chat-export",
            )
        )
    return results


def parse_paste(text: str, *, source: str = "paste") -> list[ExtractedLink]:
    seen: set[str] = set()
    results: list[ExtractedLink] = []
    for url in extract_urls_from_text(text):
        if url in seen:
            continue
        seen.add(url)
        results.append(ExtractedLink(url=url, note=f"Imported from {source}", context=source))
    return results
