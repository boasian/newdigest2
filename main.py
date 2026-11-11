#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KAOMI 오늘의 단신 2
====================
뉴스·날씨·야구·보수교육 일정 수집 → 텍스트+링크 메시지 구성 → 카카오톡 전송
"""

import json
import logging
import sys
from pathlib import Path

from news_fetcher    import fetch_news
from weather_fetcher import fetch_weather
from baseball_fetcher import fetch_kbo_yesterday, fetch_kbo_standings, is_kbo_in_season
from schedule_fetcher import fetch_schedule
from moreden_fetcher import fetch_moreden_seminars, merge_events
from message_builder import build_messages, build_weekly_seminar_message
import kakao_text_sender

BASE_DIR    = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
LOG_FILE    = BASE_DIR / "news_digest2.log"


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("NewsDigest2")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")
    for handler in [
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ]:
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def main() -> None:
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("  KAOMI 오늘의 단신 2 시작")
    logger.info("=" * 50)

    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"설정 파일 오류: {e}")
        sys.exit(1)

    # 1. 뉴스 수집
    logger.info("뉴스 수집 중...")
    naver = config["naver"]
    news = fetch_news(naver["client_id"], naver["client_secret"], count=2)
    for cat, items in news.items():
        for item in items:
            logger.info(f"  [{cat}] {item['title'][:55]}")

    # 2. 날씨 수집
    logger.info("날씨 수집 중...")
    weather = fetch_weather()
    logger.info(f"  {weather['line1']}")
    logger.info(f"  {weather['line2']}")

    # 3. 야구 결과 수집
    logger.info("KBO 결과 수집 중...")
    games = fetch_kbo_yesterday()
    standings = fetch_kbo_standings() if games else []
    # 시즌이 끝나면 야구 항목을 빼고, 경기가 다시 열리면 자동으로 포함
    show_baseball = bool(games) or is_kbo_in_season()
    logger.info(f"  경기 {len(games)}게임" + ("" if show_baseball else " (비시즌 — 야구 항목 제외)"))

    # 4. 메시지 구성 (3개)
    logger.info("메시지 구성 중...")
    msg_politics, msg_economy, msg_sports = build_messages(news, weather, games, standings, show_baseball)
    logger.info(f"  정치 {len(msg_politics)}자 / 경제 {len(msg_economy)}자 / 야구+날씨 {len(msg_sports)}자")

    # 5. 한 주간 세미나 (오늘부터 7일: 치협 보수교육 일정 + 모어덴 세미나)
    logger.info("한 주간 세미나 수집 중...")
    try:
        kda_events = fetch_schedule(days=7)
        moreden_events = fetch_moreden_seminars(days=7)
        seminars = merge_events(kda_events, moreden_events)
        msg_seminars = build_weekly_seminar_message(seminars, days=7)
        logger.info(f"  치협 {len(kda_events)}건 + 모어덴 {len(moreden_events)}건 → {len(seminars)}건 / {len(msg_seminars)}자")
    except Exception as e:
        logger.warning(f"  세미나 일정 처리 실패(세미나 메시지 생략): {e}")
        msg_seminars = ""

    # 6. 카카오톡 전송
    pc        = config.get("kakao_pc", {})
    kakao_exe = pc.get("exe_path", r"C:\Program Files (x86)\Kakao\KakaoTalk\KakaoTalk.exe")
    chat_rooms = [r for r in pc.get("chat_rooms", []) if r]

    if not chat_rooms:
        logger.error("전송할 채팅방이 설정되지 않았습니다.")
        sys.exit(1)

    for chat_name in chat_rooms:
        logger.info(f"카카오톡 전송 중... → [{chat_name}]")
        try:
            kakao_text_sender.send(msg_politics, chat_name, kakao_exe)
            logger.info(f"  [{chat_name}] 정치 전송 완료!")
            kakao_text_sender.send(msg_economy, chat_name, kakao_exe)
            logger.info(f"  [{chat_name}] 경제 전송 완료!")
            kakao_text_sender.send(msg_sports, chat_name, kakao_exe)
            logger.info(f"  [{chat_name}] 야구+날씨 전송 완료!")
            if msg_seminars:
                kakao_text_sender.send(msg_seminars, chat_name, kakao_exe)
                logger.info(f"  [{chat_name}] 한 주간 세미나 전송 완료!")
        except Exception as e:
            logger.error(f"  [{chat_name}] 전송 실패: {e}")

    logger.info("=" * 50)
    logger.info("  완료")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
