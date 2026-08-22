#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KAOMI 오늘의 단신 2
====================
뉴스 수집 → 텍스트+링크 메시지 구성 → 카카오톡 전송
"""

import json
import logging
import sys
from pathlib import Path

from news_fetcher    import fetch_news
from weather_fetcher import fetch_weather
from baseball_fetcher import fetch_kbo_yesterday, fetch_kbo_standings
from message_builder import build_messages
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
    logger.info(f"  경기 {len(games)}게임")

    # 4. 메시지 구성 (3개)
    logger.info("메시지 구성 중...")
    msg_politics, msg_economy, msg_sports = build_messages(news, weather, games, standings)
    logger.info(f"  정치 {len(msg_politics)}자 / 경제 {len(msg_economy)}자 / 야구+날씨 {len(msg_sports)}자")

    # 5. 카카오톡 전송
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
        except Exception as e:
            logger.error(f"  [{chat_name}] 전송 실패: {e}")

    logger.info("=" * 50)
    logger.info("  완료")
    logger.info("=" * 50)


if __name__ == "__main__":
    main()
