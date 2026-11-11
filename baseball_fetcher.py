#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KBO 경기 결과 및 순위 수집 — KBO 공식 사이트 API 사용."""

import re
from collections import defaultdict
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

_BASE = "https://www.koreabaseball.com"
_SCHEDULE_WS = f"{_BASE}/ws/Schedule.asmx/GetScheduleList"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": f"{_BASE}/Schedule/Schedule.aspx",
}

_SEASON_START_MONTH = 3

# 실제 KBO 10개 구단만 허용 (올스타전의 "나눔"/"드림" 등 특별 편성 팀 제외)
_KBO_TEAMS = frozenset({
    "두산", "LG", "KT", "KIA", "삼성", "한화", "NC", "롯데", "SSG", "키움",
})


def _fetch_month_games(year: int, month: int) -> list:
    try:
        r = requests.get(
            _SCHEDULE_WS,
            headers=_HEADERS,
            params={
                "leId": "1",
                "srIdList": "0,9",
                "seasonId": str(year),
                "gameMonth": f"{month:02d}",
                "teamId": "",
            },
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    rows = data.get("rows", [])
    results = []
    current_date = ""

    for row_obj in rows:
        row = row_obj.get("row", [])
        row_date = ""
        play_text = ""

        for cell in row:
            cls  = cell.get("Class", "")
            text = cell.get("Text", "") or ""
            if cls == "day":
                m = re.search(r"(\d{2}\.\d{2})", text)
                if m:
                    row_date = m.group(1)
            elif cls == "play":
                play_text = text

        if row_date:
            current_date = row_date

        if not play_text:
            continue

        soup = BeautifulSoup(play_text, "html.parser")
        em   = soup.find("em")
        if not em:
            continue

        all_spans = soup.find_all("span", recursive=False)
        if len(all_spans) < 2:
            continue
        away_team = all_spans[0].get_text(strip=True)
        home_team = all_spans[1].get_text(strip=True) if len(all_spans) > 1 else ""

        score_spans = em.find_all("span")
        scores = [s.get_text(strip=True) for s in score_spans if s.get_text(strip=True).isdigit()]
        if len(scores) < 2:
            continue

        try:
            away_score = int(scores[0])
            home_score = int(scores[1])
        except ValueError:
            continue

        results.append({
            "date": current_date,
            "away": away_team,
            "away_score": away_score,
            "home": home_team,
            "home_score": home_score,
        })

    return results


def fetch_kbo_yesterday() -> list:
    """어제 KBO 경기 결과 반환."""
    yesterday    = date.today() - timedelta(days=1)
    target_label = yesterday.strftime("%m.%d")
    games        = _fetch_month_games(yesterday.year, yesterday.month)
    return [
        {
            "away": g["away"], "away_score": g["away_score"],
            "home": g["home"], "home_score": g["home_score"],
        }
        for g in games if g["date"] == target_label
        and g["away"] in _KBO_TEAMS and g["home"] in _KBO_TEAMS
    ]


def is_kbo_in_season(days: int = 7) -> bool:
    """최근 days일 안에 KBO 경기가 있었으면 시즌 중으로 봅니다.

    시즌이 끝나면 False가 되어 단신에서 야구 항목이 빠지고,
    다음 시즌 경기가 열리면 자동으로 다시 포함됩니다.
    """
    today = date.today()
    start = today - timedelta(days=days)
    months = {(start.year, start.month), (today.year, today.month)}
    for year, month in months:
        for g in _fetch_month_games(year, month):
            if g["away"] not in _KBO_TEAMS or g["home"] not in _KBO_TEAMS:
                continue
            try:
                played = date(year, int(g["date"][:2]), int(g["date"][3:5]))
            except (ValueError, TypeError):
                continue
            if start <= played < today:
                return True
    return False


def fetch_kbo_standings() -> list:
    """시즌 누적 승패율 기준 KBO 팀 순위 반환."""
    today = date.today()
    all_games = []
    for month in range(_SEASON_START_MONTH, today.month + 1):
        all_games.extend(_fetch_month_games(today.year, month))

    today_label = today.strftime("%m.%d")
    all_games = [g for g in all_games if g["date"] <= today_label]

    # 올스타전 등 특별 편성 경기 제외 (실제 10개 구단만 순위 집계)
    all_games = [
        g for g in all_games
        if g["away"] in _KBO_TEAMS and g["home"] in _KBO_TEAMS
    ]

    record = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0})
    for g in all_games:
        away, home = g["away"], g["home"]
        as_, hs = g["away_score"], g["home_score"]
        if as_ > hs:
            record[away]["wins"]   += 1; record[home]["losses"] += 1
        elif hs > as_:
            record[home]["wins"]   += 1; record[away]["losses"] += 1
        else:
            record[away]["draws"]  += 1; record[home]["draws"]  += 1

    standings = []
    for team, rec in record.items():
        w, l = rec["wins"], rec["losses"]
        standings.append({
            "team": team, "wins": w, "losses": l,
            "draws": rec["draws"],
            "win_rate": w / (w + l) if (w + l) > 0 else 0.0,
        })

    standings.sort(key=lambda x: (-x["win_rate"], -x["wins"]))
    for i, s in enumerate(standings):
        s["rank"] = i + 1
    return standings
