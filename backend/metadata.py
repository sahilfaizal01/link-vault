from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (compatible; LinkVault/0.1; +https://localhost) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def detect_source_type(url: str, domain: str | None = None) -> str:
    host = (domain or urlparse(url).netloc or "").lower()
    path = urlparse(url).path.lower()
    if "linkedin.com" in host:
        if "/in/" in path or "/pub/" in path:
            return "linkedin_profile"
        if "/jobs/" in path:
            return "linkedin_job"
        return "linkedin"
    if any(x in host for x in ("youtube.com", "youtu.be", "vimeo.com")):
        return "video"
    if any(x in host for x in ("twitter.com", "x.com")):
        return "social"
    if any(x in host for x in ("medium.com", "substack.com", "dev.to", "hashnode")):
        return "blog"
    return "article"


def _meta_content(soup: BeautifulSoup, *names: str) -> str | None:
    for name in names:
        tag = soup.find("meta", attrs={"name": name}) or soup.find(
            "meta", attrs={"property": name}
        )
        if tag and tag.get("content"):
            text = str(tag["content"]).strip()
            if text:
                return text
    return None


def _clean_text(text: str, max_len: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


async def fetch_page_metadata(url: str) -> dict[str, str | None]:
    domain = urlparse(url).netloc.replace("www.", "")
    source_type = detect_source_type(url, domain)
    title: str | None = None
    description: str | None = None
    excerpt: str | None = None

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            title = _meta_content(
                soup, "og:title", "twitter:title", "title"
            ) or (soup.title.string.strip() if soup.title and soup.title.string else None)
            description = _meta_content(
                soup,
                "og:description",
                "twitter:description",
                "description",
            )

            paragraphs = [
                p.get_text(" ", strip=True)
                for p in soup.find_all("p")
                if len(p.get_text(strip=True)) > 40
            ]
            if paragraphs:
                excerpt = _clean_text(" ".join(paragraphs[:3]))
            elif description:
                excerpt = _clean_text(description)
    except Exception:
        # LinkedIn and some sites block bots; we still store the URL.
        pass

    return {
        "domain": domain,
        "source_type": source_type,
        "title": title,
        "description": description,
        "excerpt": excerpt,
    }
