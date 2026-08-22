#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""네이버 날씨 검색 결과에서 서울 날씨를 가져옵니다 (기상청 데이터 기반, API 키 불필요)."""

import logging
import re
import time

import requests
from bs4 import BeautifulSoup

_log = logging.getLogger("NewsDigest2")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _text_no_blind(el) -> str:
    for b in el.select(".blind"):
        b.decompose()
    return el.get_text(strip=True)


def _fetch_once() -> dict:
    r = requests.get(
        "https://search.naver.com/search.naver",
        params={"query": "서울날씨"},
        headers=_HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    today_row = soup.select_one("li.week_item.today")
    if today_row is None:
        raise ValueError("오늘자 예보 항목을 찾을 수 없음 (네이버 페이지 구조 변경 가능성)")

    low_el  = today_row.select_one(".lowest")
    high_el = today_row.select_one(".highest")
    if low_el is None or high_el is None:
        raise ValueError("최저/최고 기온을 찾을 수 없음")

    t_min = int(re.sub(r"[^\d-]", "", _text_no_blind(low_el)))
    t_max = int(re.sub(r"[^\d-]", "", _text_no_blind(high_el)))

    cond_el = soup.select_one(".weather.before_slash")
    desc_ko = cond_el.get_text(strip=True) if cond_el else "정보 없음"

    # 오전/오후 강수확률 중 최댓값
    rain_pct = 0
    for cell in today_row.select(".cell_weather"):
        for pct in re.findall(r"(\d+)%", cell.get_text()):
            rain_pct = max(rain_pct, int(pct))

    if "눈" in desc_ko:
        tip = "빙판길 조심하세요"
    elif "비" in desc_ko or rain_pct >= 50:
        tip = "우산을 챙기세요"
    elif t_max >= 33:
        tip = "폭염 주의, 수분 보충에 신경 쓰세요"
    elif t_min <= 0:
        tip = "방한에 신경 쓰세요"
    elif (t_max - t_min) >= 10:
        tip = "큰 일교차에 건강 유의하세요"
    else:
        tip = "건강한 하루 보내세요"

    return {
        "line1": f"서울 {desc_ko}, {tip}",
        "line2": f"최저 {t_min}도 / 최고 {t_max}도",
    }


def fetch_weather(city: str = "Seoul") -> dict:
    for attempt in range(1, 3):
        try:
            return _fetch_once()
        except Exception as e:
            _log.warning(f"  날씨 수집 실패 ({attempt}/2): {e}")
            if attempt < 2:
                time.sleep(5)

    return {
        "line1": "날씨 정보를 가져올 수 없습니다",
        "line2": "기상청 앱에서 확인해주세요",
    }
