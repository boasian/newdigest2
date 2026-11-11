#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""치과의사 보수교육·학술 일정 수집 — 대한치과의사협회 보수교육센터(edu.kda.or.kr).

보수교육센터 '보수교육일정' 메뉴가 쓰는 공개 조회 주소를 그대로 호출합니다 (로그인 불필요).
오늘부터 days일 동안 열리는 교육을 날짜순으로 반환하며,
조회에 실패하면 빈 목록을 반환해 단신 전송에는 영향을 주지 않습니다.
"""

import logging
import re
from datetime import date, datetime, timedelta

import requests

_log = logging.getLogger("NewsDigest2")

_BASE = "https://edu.kda.or.kr"
_LIST_URL = f"{_BASE}/user/schedule/selectScheduleList.kda"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{_BASE}/user/schedule/scheduleList.kda",
}

_MAX_PAGES = 40          # 한 달 최대 400건까지 조회
_MAX_COURSE_DAYS = 7     # 이보다 긴 일정은 장기 연수과정으로 보고 제외


def _fetch_month(year: int, month: int) -> list:
    """해당 월의 보수교육 일정 전체(여러 페이지)를 가져옵니다."""
    items = []
    for page in range(1, _MAX_PAGES + 1):
        r = requests.post(
            _LIST_URL,
            headers=_HEADERS,
            data={
                "pageIndex": str(page),
                "srchArea": "",
                "srchTitle": "",
                "srchOrgName": "",
                "planYear": str(year),
                "planMonth": f"{month:02d}",
                "planType": "",
                "passNo": "3",
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("scheduleList") or []
        items.extend(rows)
        total = int(data.get("totalCount") or 0)
        if not rows or len(items) >= total:
            break
    return items


_URL_RE = re.compile(r"(https?://[^\s\[\]()<>\"']+|www\.[^\s\[\]()<>\"']+)", re.IGNORECASE)


def extract_url(text) -> str:
    """안내 문구가 섞인 값에서 웹 주소만 뽑습니다. 주소가 없으면 빈 문자열."""
    text = str(text or "").strip()
    m = _URL_RE.search(text)
    if not m:
        # 'forms.gle/abc'처럼 http·www 없이 주소만 적은 경우
        if re.fullmatch(r"[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+(/[^\s@]*)?", text):
            return "http://" + text
        return ""
    url = m.group(1).rstrip(".,;:-")
    if "." not in url.split("//")[-1]:
        return ""
    return url if url.lower().startswith("http") else "http://" + url


def _parse_ymd(value) -> date | None:
    try:
        return datetime.strptime(str(value)[:8], "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def fetch_schedule(days: int = 7) -> list:
    """오늘부터 days일 동안의 보수교육·학술 일정을 반환합니다.

    각 항목: start, end(date), time, area, org, title, score(총점), required(필수점수), link(등록 주소)
    """
    today = date.today()
    last = today + timedelta(days=days - 1)
    months = sorted({(today.year, today.month), (last.year, last.month)})

    raw = []
    try:
        for year, month in months:
            raw.extend(_fetch_month(year, month))
    except Exception as e:
        _log.warning(f"  보수교육 일정 조회 실패: {e}")
        return []

    events, seen = [], set()
    for item in raw:
        start = _parse_ymd(item.get("frymd"))
        end = _parse_ymd(item.get("toymd")) or start
        if start is None:
            continue
        if end < today or start > last:
            continue                                  # 조회 기간 밖
        if (end - start).days > _MAX_COURSE_DAYS:
            continue                                  # 수개월짜리 연수과정 제외

        key = item.get("planno") or (item.get("lectitle"), item.get("frymd"), item.get("frtime"))
        if key in seen:
            continue
        seen.add(key)

        jumsu, req = _to_int(item.get("jumsu")), _to_int(item.get("reqjumsu"))
        if str(item.get("plantype")) == "8":          # 필수교육만 있는 과정
            score, required = jumsu, jumsu
        else:
            score, required = jumsu + req, req

        title = " ".join(str(item.get("lectitle") or "").split())
        events.append({
            "start": start,
            "end": end,
            "time": str(item.get("frtime") or "").strip(),
            "area": str(item.get("branchname") or "").strip(),
            "org": str(item.get("gigwanname") or "").strip(),
            "title": title,
            "score": score,
            "required": required,
            "link": extract_url(item.get("regpage")),
        })

    events.sort(key=lambda e: (e["start"], e["time"], e["org"]))
    return events
