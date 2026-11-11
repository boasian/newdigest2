#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""보수교육 점수가 없는 일반 세미나 일정 수집 — 모어덴(moreden.co.kr) 세미나 게시판.

모어덴 세미나 페이지가 쓰는 공개 목록 주소를 호출합니다 (로그인 불필요).
게시판은 등록일 순이라 최근 게시글을 여러 페이지 훑어서 오늘부터 days일 안에 열리는 것만 고릅니다.
같은 세미나를 여러 번 올린 홍보글은 하나로 합칩니다.
merge_events()가 치협 보수교육센터 일정(schedule_fetcher)과 합치면서 겹치는 행사를 정리합니다.
조회에 실패하면 빈 목록을 반환해 단신 전송에는 영향을 주지 않습니다.
"""

import json
import logging
import re
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

import requests

from schedule_fetcher import extract_url

_log = logging.getLogger("NewsDigest2")

_POST_URL = "https://moreden.co.kr/management/seminar/{bid}"
_LIST_URL = "https://public-api.moreden.co.kr/community/management/seminar/list"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://moreden.co.kr/management/seminar",
}

_MAX_PAGES = 25          # 한 페이지 20건 — 대략 최근 3~4개월 게시글
_MAX_COURSE_DAYS = 7     # 이보다 긴 일정은 장기 연수과정으로 보고 제외


def _parse_ymd(value) -> date | None:
    try:
        return datetime.strptime(str(value)[:8], "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def _norm(text: str) -> str:
    """비교용: 한글·영문·숫자만 남기고 소문자로."""
    return re.sub(r"[^0-9a-z가-힣]", "", str(text or "").lower())


def _clean_title(title: str, host: str) -> str:
    """홍보용 기호·이모지를 걷어내고, 제목 앞의 【주최】 표기가 주최와 같으면 뺍니다."""
    t = re.sub(r"[^\w\s가-힣.,:;!?&/+~%·'\"()\[\]<>【】『』「」-]", " ", str(title or ""))
    t = re.sub(r"[!?~.]{2,}", " ", t)
    m = re.match(r"\s*[\[【]([^\]】]{1,30})[\]】]\s*(.+)", t)
    if m and host and (_norm(m.group(1)) in _norm(host) or _norm(host) in _norm(m.group(1))):
        t = m.group(2)
    return " ".join(t.split()).strip(" -·:")


def _area(item: dict) -> str:
    if "온라인" in str(item.get("location") or ""):
        return "온라인"
    cities = item.get("locationCities")
    if isinstance(cities, str):
        try:
            cities = json.loads(cities)
        except ValueError:
            cities = []
    names = [str(c.get("name")) for c in (cities or []) if isinstance(c, dict) and c.get("name")]
    if not names:
        return ""
    return names[0] if len(names) == 1 else f"{names[0]} 외"


def _is_duplicate(a: dict, b: dict) -> bool:
    if a["start"] != b["start"]:
        return False
    ha, hb = _norm(a["org"]), _norm(b["org"])
    if len(ha) >= 2 and len(hb) >= 2 and (ha in hb or hb in ha):
        return True
    return SequenceMatcher(None, _norm(a["title"]), _norm(b["title"])).ratio() >= 0.6


def fetch_moreden_seminars(days: int = 7) -> list:
    """오늘부터 days일 동안 열리는 모어덴 게시 세미나를 날짜순으로 반환합니다.

    각 항목: start, end(date), time(빈 값), area, org, title, score, required, link
    link는 게시글에 적힌 홈페이지 주소, 없으면 모어덴 게시글 주소입니다.
    """
    today = date.today()
    last = today + timedelta(days=days - 1)

    raw = []
    try:
        for page in range(1, _MAX_PAGES + 1):
            r = requests.get(_LIST_URL, headers=_HEADERS, params={"page": page}, timeout=10)
            r.raise_for_status()
            data = r.json()
            board = data.get("board") or []
            raw.extend(board)
            if not board or page >= int(data.get("pages") or 0):
                break
    except Exception as e:
        _log.warning(f"  모어덴 세미나 조회 중단({len(raw)}건까지 사용): {e}")

    events = []
    for item in raw:                      # 최신 게시글부터 — 중복이면 먼저 본(최신) 글을 남김
        if item.get("deleted"):
            continue
        try:
            score = int(item.get("point") or 0)
        except (ValueError, TypeError):
            score = 0
        start = _parse_ymd(item.get("start_date"))
        end = _parse_ymd(item.get("end_date")) or start
        if start is None or end < today or start > last:
            continue
        if (end - start).days > _MAX_COURSE_DAYS:
            continue

        host = " ".join(str(item.get("host") or "").split()).strip(" .")
        title = _clean_title(item.get("title"), host)
        if not title or "취소" in title:
            continue
        ev = {
            "start": start,
            "end": end,
            "area": _area(item),
            "org": host,
            "title": title,
            "time": "",
            "score": score,
            "required": 0,
            "link": extract_url(item.get("website"))
                    or (_POST_URL.format(bid=item["bid"]) if item.get("bid") else ""),
        }
        if any(_is_duplicate(ev, other) for other in events):
            continue
        events.append(ev)

    events.sort(key=lambda e: (e["start"], e["area"] != "온라인", e["org"]))
    return events


def merge_events(kda_events: list, moreden_events: list) -> list:
    """치협 보수교육 일정과 모어덴 세미나를 하나로 합칩니다.

    같은 행사가 양쪽에 있으면 치협 쪽(점수·시간이 정확)을 남기고,
    치협 쪽에 등록 주소가 없을 때만 모어덴 쪽 주소를 가져옵니다.
    """
    merged = [dict(e) for e in kda_events]
    for ev in moreden_events:
        twin = next((k for k in merged if _is_duplicate(ev, k)), None)
        if twin is not None:
            if not twin.get("link") and ev.get("link"):
                twin["link"] = ev["link"]
            continue
        merged.append(dict(ev))
    merged.sort(key=lambda e: (e["start"], e.get("time") or "99:99", e.get("org") or ""))
    return merged

