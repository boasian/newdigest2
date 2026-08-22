#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAOMI 오늘의 단신 2 아이콘(.ico) 생성"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

BASE_DIR = Path(__file__).parent


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    r  = s // 8
    bg = (18, 80, 99)        # 틸 계열 (단신2 구분색)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=bg)

    margin   = s * 0.10
    pad      = s * 0.06
    header_h = s * 0.22
    header_y1 = margin
    header_y2 = margin + header_h

    d.rounded_rectangle(
        [margin, header_y1, s - margin, header_y2],
        radius=r // 2,
        fill=(245, 240, 220),
    )

    try:
        font_big = ImageFont.truetype("arialbd.ttf", int(header_h * 0.72))
    except OSError:
        font_big = ImageFont.load_default()

    text = "NEWS"
    bbox = font_big.getbbox(text)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (s - tw) / 2 - bbox[0]
    ty = header_y1 + (header_h - th) / 2 - bbox[1]
    d.text((tx, ty), text, font=font_big, fill=(18, 80, 99))

    line_color = (180, 215, 225)
    line_h     = max(2, s // 40)
    gap        = s * 0.055
    col_gap    = s * 0.04
    col_w      = (s - margin * 2 - col_gap) / 2

    y = header_y2 + pad * 1.4
    for row in range(5):
        for col in range(2):
            x1 = margin + col * (col_w + col_gap)
            x2 = x1 + col_w * (0.85 if row == 4 else 1.0)
            y1 = y + row * gap
            y2 = y1 + line_h
            if y2 < s - margin:
                d.rounded_rectangle([x1, y1, x2, y2], radius=line_h // 2, fill=line_color)

    try:
        font_sm = ImageFont.truetype("arial.ttf", max(6, int(s * 0.10)))
    except OSError:
        font_sm = ImageFont.load_default()

    label = "KAOMI 2"
    bbox2 = font_sm.getbbox(label)
    lw = bbox2[2] - bbox2[0]
    lx = (s - lw) / 2 - bbox2[0]
    ly = s - margin - (bbox2[3] - bbox2[1]) - bbox2[1]
    d.text((lx, ly), label, font=font_sm, fill=(150, 210, 225))

    return img


def main():
    sizes  = [256, 64, 48, 32, 16]
    images = [draw_icon(sz) for sz in sizes]

    ico_path = BASE_DIR / "kaomi_news2.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(sz, sz) for sz in sizes],
        append_images=images[1:],
    )
    print(f"아이콘 생성 완료: {ico_path}")


if __name__ == "__main__":
    main()
