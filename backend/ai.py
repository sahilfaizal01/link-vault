from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from .buckets import CANONICAL_BUCKETS, DEFAULT_BUCKET, classify_bucket
from .config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_USER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


def _build_client() -> OpenAI | None:
    if OPENAI_API_KEY:
        return OpenAI(api_key=OPENAI_API_KEY)
    if LLM_API_KEY and LLM_BASE_URL:
        headers: dict[str, str] = {"Ocp-Apim-Subscription-Key": LLM_API_KEY}
        if LLM_USER:
            headers["user"] = LLM_USER
        return OpenAI(api_key="dummy", base_url=LLM_BASE_URL, default_headers=headers)
    return None


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _heuristic_analysis(
    *,
    url: str,
    title: str | None,
    description: str | None,
    excerpt: str | None,
    source_type: str,
) -> dict[str, Any]:
    blob = " ".join(
        filter(
            None,
            [url, title or "", description or "", excerpt or "", source_type],
        )
    ).lower()

    bucket, tags = classify_bucket(url, blob, source_type)

    summary_source = description or excerpt or title or url
    summary = (summary_source or "")[:280]
    if len(summary_source or "") > 280:
        summary += "..."

    return {
        "summary": summary,
        "why_it_matters": "Saved for later review in your personal knowledge feed.",
        "bucket": bucket,
        "tags": tags or [source_type, "saved-link"],
    }


async def analyze_link(
    *,
    url: str,
    title: str | None,
    description: str | None,
    excerpt: str | None,
    note: str | None,
    source_type: str,
) -> dict[str, Any]:
    client = _build_client()
    if not client:
        return _heuristic_analysis(
            url=url,
            title=title,
            description=description,
            excerpt=excerpt,
            source_type=source_type,
        )

    model = OPENAI_MODEL if OPENAI_API_KEY else LLM_MODEL
    prompt = f"""
You organize saved links for an ML/GPU engineer who tracks LinkedIn profiles, jobs, and technical reading.
Pick exactly ONE bucket from this list:
{", ".join(CANONICAL_BUCKETS)}

Guidance:
- linkedin.com/in/ → LinkedIn Profiles
- job postings / careers pages → Job Links
- CUDA/ROCm/kernels → GPU Programming
- serving, quantization, vLLM, TensorRT → Inference Optimization
- transformer/MoE/architecture posts → Model Architecture
- fine-tuning, pretraining, RLHF → Training
- short practical threads → Tips & Tricks

Return ONLY valid JSON with keys:
summary (2 sentences), why_it_matters (1 sentence), bucket, tags (array of 3-6 short strings).

URL: {url}
Source type: {source_type}
Title: {title or "unknown"}
Description: {description or "n/a"}
Excerpt: {excerpt or "n/a"}
User note: {note or "n/a"}
""".strip()

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_completion_tokens=400,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You classify technical and career links for a GPU/ML engineer. "
                        "Use only the provided bucket names. Output JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = _extract_json(content)
        bucket = data.get("bucket") or DEFAULT_BUCKET
        if bucket not in CANONICAL_BUCKETS:
            text_blob = " ".join(
                filter(None, [title or "", description or "", excerpt or "", note or ""])
            )
            bucket, _ = classify_bucket(url, text_blob, source_type)
        return {
            "summary": str(data.get("summary") or description or title or url)[:500],
            "why_it_matters": str(
                data.get("why_it_matters")
                or "Useful reference to revisit when you have focused reading time."
            )[:300],
            "bucket": bucket,
            "tags": list(data.get("tags") or [])[:8],
        }
    except Exception:
        return _heuristic_analysis(
            url=url,
            title=title,
            description=description,
            excerpt=excerpt,
            source_type=source_type,
        )


async def build_digest(items: list[dict[str, Any]]) -> dict[str, Any]:
    if not items:
        return {
            "headline": "No saved links yet",
            "overview": "Save a few links from the extension or dashboard to generate your first digest.",
            "top_insights": [],
            "buckets": [],
            "read_next": [],
        }

    by_bucket: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        bucket = item.get("bucket") or "Unsorted"
        by_bucket.setdefault(bucket, []).append(item)

    buckets = [
        {
            "name": name,
            "count": len(group),
            "highlight": group[0].get("summary") or group[0].get("title"),
        }
        for name, group in sorted(by_bucket.items(), key=lambda x: len(x[1]), reverse=True)
    ]

    read_next = [
        {
            "id": item["id"],
            "title": item.get("title") or item.get("url"),
            "url": item["url"],
            "bucket": item.get("bucket"),
            "why": item.get("why_it_matters"),
        }
        for item in items[:5]
    ]

    client = _build_client()
    if not client:
        return {
            "headline": f"Your reading queue: {len(items)} links across {len(buckets)} themes",
            "overview": "Grouped automatically by topic. Start with the largest bucket or pick from Read Next.",
            "top_insights": [
                f"{b['name']}: {b['count']} links" for b in buckets[:5]
            ],
            "buckets": buckets,
            "read_next": read_next,
        }

    model = OPENAI_MODEL if OPENAI_API_KEY else LLM_MODEL
    compact = [
        {
            "title": i.get("title"),
            "bucket": i.get("bucket"),
            "summary": i.get("summary"),
            "url": i.get("url"),
        }
        for i in items[:40]
    ]
    prompt = f"""
Create a weekly reading digest from these saved links.
Return ONLY JSON with keys: headline, overview (2-3 sentences), top_insights (array of 5 bullets), read_next (array of 5 objects with title, url, bucket, why).

Links:
{json.dumps(compact, indent=2)}
""".strip()

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.4,
            max_completion_tokens=700,
            messages=[
                {"role": "system", "content": "You write concise, actionable reading digests."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = _extract_json(content)
        data["buckets"] = buckets
        return data
    except Exception:
        return {
            "headline": f"Your reading queue: {len(items)} links",
            "overview": "AI digest unavailable; showing structured bucket view instead.",
            "top_insights": [b["highlight"] for b in buckets[:5] if b.get("highlight")],
            "buckets": buckets,
            "read_next": read_next,
        }
