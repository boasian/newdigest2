#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수집된 뉴스·날씨·야구 데이터를 카카오톡 전송용 텍스트로 변환합니다."""

from datetime import date, timedelta

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
_NUM_EMOJI  = ["①", "②", "③", "④", "⑤"]
_RANK_EMOJI = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
_SEP = "━" * 22


def build_messages(news: dict, weather: dict,
                   games: list, standings: list) -> tuple[str, str, str]:
    """(정치 메시지, 경제 메시지, 야구+날씨 메시지) 세 개를 반환합니다."""
    today   = date.today()
    weekday = _WEEKDAY_KO[today.weekday()]
    header  = f"{today.year}년 {today.month}월 {today.day}일 ({weekday})"

    def _news_block(cat: str, emoji: str, items: list) -> str:
        lines = ["📰 KAOMI 오늘의 단신", _SEP, header, "", f"{emoji} {cat}", ""]
        for i, item in enumerate(items):
            num = _NUM_EMOJI[i] if i < len(_NUM_EMOJI) else f"{i+1}."
            lines.append(f"{num} {item['title']}")
            if item.get("summary"):
                lines.append(item["summary"])
            if item.get("url"):
                lines.append(f"🔗 {item['url']}")
            lines.append("")
        lines.append(_SEP)
        return "\n".join(lines)

    m1 = _news_block("정치", "🏛", news.get("정치", []))
    m2 = _news_block("경제", "💰", news.get("경제", []))

    # ── 메시지 3: 야구 + 날씨 ────────────────────────────────────
    yesterday = today - timedelta(days=1)
    m3 = []

    if games:
        parts = [f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']}"
                 for g in games]
        game_lines = ["   ".join(parts[i:i+3]) for i in range(0, len(parts), 3)]
        m3.append(f"⚾ KBO 경기결과 ({yesterday.month}월 {yesterday.day}일)")
        m3.extend(game_lines)
        if standings:
            rank_str = " ".join(
                f"{_RANK_EMOJI[i]}{s['team']}"
                for i, s in enumerate(standings[:10])
            )
            m3 += ["", "팀 순위", rank_str]
    else:
        m3.append(f"⚾ KBO ({yesterday.month}월 {yesterday.day}일) 경기 없음")

    m3 += ["", _SEP, "🌤 서울 날씨"]
    if weather.get("line1"):
        m3.append(weather["line1"])
    if weather.get("line2"):
        m3.append(weather["line2"])
    m3.append(_SEP)

    return m1, m2, "\n".join(m3)
