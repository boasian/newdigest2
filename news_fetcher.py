#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""네이버 뉴스 검색 API로 정치·경제 뉴스를 수집합니다 (제목 + 요약 + 원문 링크)."""

import html
import re
import requests
from urllib.parse import urlparse

URL = "https://openapi.naver.com/v1/search/news.json"
_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

QUERIES = {
    "정치": "국내 정치 국회",
    "경제": "경제 증시 금융",
}

_VIDEO_KW = {"[영상]", "(영상)", "영상clip", "영상 clip", "[클립]", "(클립)"}


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    prev = None
    while prev != text:
        prev = text
        text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _is_domestic(url: str) -> bool:
    try:
        host = urlparse(url).hostname or ""
        return host.endswith(".kr") or "naver.com" in host
    except Exception:
        return True


_DEAD_PAGE_KW = [
    "페이지를 찾을 수 없", "존재하지 않는 페이지", "삭제된 기사", "삭제된 게시물",
    "요청하신 페이지를 찾을 수 없", "해당 기사를 찾을 수 없", "해당 페이지를 찾을 수 없",
    "이동된 페이지", "잘못된 접근", "Page not found", "404 Not Found", "찾을 수 없는 페이지",
]


def _fetch_article_info(url: str) -> dict:
    """기사 URL에서 og:title, og:description, 최종 URL을 가져오고, 실제로 열리는 링크인지 확인합니다."""
    result = {"title": None, "summary": "", "url": url, "ok": False}
    try:
        r = requests.get(url, headers=_UA, timeout=8, allow_redirects=True)
        result["url"] = r.url  # 리다이렉트 후 최종 URL
        if r.status_code != 200:
            return result

        ct = r.headers.get("Content-Type", "")
        m_enc = re.search(r"charset=([\w-]+)", ct, re.IGNORECASE)
        enc = m_enc.group(1) if m_enc else (r.apparent_encoding or "utf-8")
        try:
            page = r.content.decode(enc, errors="replace")
        except Exception:
            page = r.content.decode("utf-8", errors="replace")

        for pat in [
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']{5,})["\']',
            r'<meta[^>]+content=["\']([^"\']{5,})["\'][^>]+property=["\']og:title["\']',
        ]:
            m = re.search(pat, page, re.IGNORECASE)
            if m:
                result["title"] = _clean(m.group(1))
                break

        if not result["title"]:
            m = re.search(r'<title[^>]*>([^<]{5,})</title>', page)
            if m:
                t = _clean(m.group(1))
                for sep in [" | ", " - ", " :: ", " · ", " > "]:
                    if sep in t:
                        t = t.split(sep)[0].strip()
                result["title"] = t

        for pat in [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']{15,})["\']',
            r'<meta[^>]+content=["\']([^"\']{15,})["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{15,})["\']',
            r'<meta[^>]+content=["\']([^"\']{15,})["\'][^>]+name=["\']description["\']',
        ]:
            m = re.search(pat, page, re.IGNORECASE)
            if m:
                desc = _clean(m.group(1))
                if len(desc) >= 15:
                    result["summary"] = desc
                    break

        check_text = (result["title"] or "") + " " + page[:3000]
        if any(kw.lower() in check_text.lower() for kw in _DEAD_PAGE_KW):
            return result  # 에러/삭제 페이지로 판단 -> ok는 False로 유지

        result["ok"] = True

    except Exception:
        pass
    return result


def _trim(text: str, max_len: int = 120) -> str:
    if not text or len(text) <= max_len:
        return text
    for end in [".", "!", "?", "。", "…"]:
        idx = text.rfind(end, 0, max_len)
        if idx > max_len * 0.5:
            return text[:idx + 1]
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    return (truncated[:last_space] if last_space > 0 else truncated) + "…"


def fetch_news(client_id: str, client_secret: str, count: int = 2) -> dict:
    """카테고리별 뉴스를 count개 수집합니다.
    반환값: {"정치": [{"title", "summary", "url"}, ...], "경제": [...]}
    """
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    result = {}

    for cat, query in QUERIES.items():
        try:
            r = requests.get(
                URL,
                headers=headers,
                params={"query": query, "display": 30, "sort": "date"},
                timeout=10,
            )
            r.raise_for_status()
            items = r.json().get("items", [])

            collected = []
            for it in items:
                if not it.get("title"):
                    continue

                title = _clean(it["title"])
                description = _clean(it.get("description", ""))
                url = it.get("originallink") or it.get("link", "")

                if any(kw.lower() in title.lower() for kw in _VIDEO_KW):
                    continue
                if url and not _is_domestic(url):
                    continue

                if not url:
                    continue  # 원문 링크가 없는 뉴스는 확인이 불가능하므로 건너뜀

                info = _fetch_article_info(url)
                if not info["ok"]:
                    continue  # 링크 접속 실패/삭제된 기사 -> 다음 뉴스 후보로

                final_url = info["url"] or url
                if info["title"]:
                    title = info["title"]
                elif title.endswith("...") or title.endswith("…"):
                    title = title.rstrip(".…").strip()
                summary = _trim(info["summary"] or description)

                collected.append({"title": title, "summary": summary, "url": final_url})
                if len(collected) >= count:
                    break

            result[cat] = collected or [{"title": f"{cat} 뉴스 없음", "summary": "", "url": ""}]

        except Exception:
            result[cat] = [{"title": f"{cat} 뉴스 수집 실패", "summary": "", "url": ""}]

    return result
