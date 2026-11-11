#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""수집된 뉴스·날씨·야구 데이터를 카카오톡 전송용 텍스트로 변환합니다."""

from datetime import date, timedelta

_WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
_NUM_EMOJI  = ["①", "②", "③", "④", "⑤"]
_RANK_EMOJI = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
_SEP = "━" * 22


def build_messages(news: dict, weather: dict,
                   games: list, standings: list,
                   show_baseball: bool = True) -> tuple[str, str, str]:
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
    elif show_baseball:
        m3.append(f"⚾ KBO ({yesterday.month}월 {yesterday.day}일) 경기 없음")
    # 비시즌(show_baseball=False)에는 야구 항목 없이 날씨만 보냅니다.

    if m3:
        m3.append("")
    m3 += [_SEP, "🌤 서울 날씨"]
    if weather.get("line1"):
        m3.append(weather["line1"])
    if weather.get("line2"):
        m3.append(weather["line2"])
    m3.append(_SEP)

    return m1, m2, "\n".join(m3)


def _md(d: date) -> str:
    return f"{d.month}/{d.day}({_WEEKDAY_KO[d.weekday()]})"


def _score(e: dict) -> str:
    if not e.get("score"):
        return ""
    txt = f"{e['score']}점"
    if e.get("required"):
        txt += f"(필수 {e['required']})"
    return txt


_MAX_PER_DAY = 3      # 하루에 보여줄 세미나 최대 개수


def _is_branch(e: dict) -> bool:
    """치협 시·도 지부가 주최하는 세미나(서울지부, 인천지부 …)인지."""
    return str(e.get("org") or "").strip().endswith("지부")


def build_weekly_seminar_message(events: list, days: int = 7) -> str:
    """오늘부터 days일간의 세미나(보수교육 + 그 외)를 날짜별로 묶은 메시지. 없으면 빈 문자열.

    지부 세미나는 제외하고, 하루 최대 _MAX_PER_DAY개만 보여줍니다.
    보수교육 점수가 있는 것을 먼저, 그다음 등록 링크가 있는 것,
    그 안에서는 점수가 높은 것, 시작 시간이 이른 것 순입니다.
    """
    today = date.today()
    last  = today + timedelta(days=days - 1)

    def _day(e: dict) -> date:          # 이미 시작한 여러 날 행사는 오늘 날짜 아래에 표시
        return max(e["start"], today)

    by_day = {}
    for e in events:
        if not _is_branch(e):
            by_day.setdefault(_day(e), []).append(e)
    if not by_day:
        return ""

    lines = [f"📅 한 주간 세미나 ({_md(today)}~{_md(last)})", _SEP]
    for n, day in enumerate(sorted(by_day)):
        picked = sorted(
            by_day[day],
            key=lambda x: (not x.get("score"), not x.get("link"), -(x.get("score") or 0),
                           x.get("time") or "99:99", x.get("org") or ""),
        )[:_MAX_PER_DAY]
        if n:
            lines.append("")
        lines.append(f"[{_md(day)}]")
        for e in picked:
            head = " ".join(x for x in (e.get("time"), e.get("area"), e.get("org")) if x)
            body = e["title"]                      # 제목은 줄이지 않고 전체 표시
            if e["end"] != e["start"]:
                body += f" (~{_md(e['end'])})"
            score = _score(e)
            lines.append((f"▪ {head} — {body}" if head else f"▪ {body}") + (f" · {score}" if score else ""))
            if e.get("link"):
                lines.append(f"   🔗 {e['link']}")

    lines += ["", _SEP, "점수 표시는 치협 보수교육 점수", "출처: 치협 보수교육센터 · 모어덴 세미나"]
    return "\n".join(lines)
