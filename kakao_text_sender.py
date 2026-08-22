#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""카카오톡 PC 앱 자동화 — 채팅창에 텍스트(링크 포함) 메시지 전송."""

import ctypes
import ctypes.wintypes
import logging
import time

import win32api
import win32clipboard
import win32con
import win32gui
import win32process

_log = logging.getLogger("NewsDigest2")
_user32 = ctypes.windll.user32

INPUT_MOUSE          = 0
INPUT_KEYBOARD       = 1
MOUSEEVENTF_MOVE     = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VDESK    = 0x4000
KEYEVENTF_KEYUP      = 0x0002
ES_READONLY          = 0x0800
GWL_STYLE            = -16
GA_ROOT              = 2

SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
SPIF_SENDCHANGE              = 0x0002

VK_CTRL   = 0x11
VK_A      = 0x41
VK_V      = 0x56
VK_DELETE = 0x2E
VK_RETURN = 0x0D
UP        = KEYEVENTF_KEYUP


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx",          ctypes.c_long),
                ("dy",          ctypes.c_long),
                ("mouseData",   ctypes.c_ulong),
                ("dwFlags",     ctypes.c_ulong),
                ("time",        ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk",         ctypes.c_ushort),
                ("wScan",       ctypes.c_ushort),
                ("dwFlags",     ctypes.c_ulong),
                ("time",        ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_size_t)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("_u",)
    _fields_    = [("type", ctypes.c_ulong), ("_u", _U)]


_SZ = ctypes.sizeof(INPUT)


def _force_foreground(hwnd: int) -> bool:
    _user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, None, SPIF_SENDCHANGE)
    VK_MENU = 0x12
    alt = (INPUT * 2)(
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_MENU, dwFlags=0)),
        INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=VK_MENU, dwFlags=KEYEVENTF_KEYUP)),
    )
    _user32.SendInput(2, alt, _SZ)
    _user32.ShowWindow(hwnd, 9)
    time.sleep(0.15)
    _user32.SetForegroundWindow(hwnd)
    _user32.BringWindowToTop(hwnd)
    time.sleep(0.5)
    fg = _user32.GetForegroundWindow()
    ok = (fg == hwnd) or (_user32.GetAncestor(fg, GA_ROOT) == hwnd)
    _log.info(f"  [TEXT] ForceForground ok={ok}  fg={fg:#010x}  want={hwnd:#010x}")
    return ok


def _find_kakao_chat_window(chat_name: str) -> int | None:
    kakao_pid = None

    def find_main(hwnd, _):
        nonlocal kakao_pid
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == "카카오톡":
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            kakao_pid = pid

    win32gui.EnumWindows(find_main, None)
    if not kakao_pid:
        return None

    result = []

    def find_chat(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and chat_name in win32gui.GetWindowText(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == kakao_pid:
                result.append(hwnd)

    win32gui.EnumWindows(find_chat, None)
    return result[0] if result else None


def _find_input_richedit(parent_hwnd: int) -> int | None:
    all_children = []
    candidates = []

    def enum_child(hwnd, _):
        cls  = win32gui.GetClassName(hwnd)
        rect = win32gui.GetWindowRect(hwnd)
        text = ""
        try:
            text = win32gui.GetWindowText(hwnd)
        except Exception:
            pass
        all_children.append({"hwnd": hwnd, "cls": cls, "rect": rect, "text": text})
        if "RICHEDIT50W" in cls:
            style       = _user32.GetWindowLongW(hwnd, GWL_STYLE)
            is_readonly = bool(style & ES_READONLY)
            candidates.append({"hwnd": hwnd, "readonly": is_readonly,
                                "rect": rect, "height": rect[3] - rect[1]})

    win32gui.EnumChildWindows(parent_hwnd, enum_child, None)

    for c in all_children:
        r = c["rect"]
        _log.info(f"  [TEXT] child hwnd={c['hwnd']} cls={c['cls']!r} "
                  f"rect=({r[0]},{r[1]},{r[2]},{r[3]}) text={c['text']!r}")

    if not candidates:
        return None

    writable = [c for c in candidates if not c["readonly"]]
    pool     = writable if writable else candidates
    chosen   = max(pool, key=lambda c: c["rect"][1])
    _log.info(f"  [TEXT] 입력창 선택: hwnd={chosen['hwnd']}")
    return chosen["hwnd"]


def _set_clipboard(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def send(text: str, chat_name: str,
         kakao_exe: str = r"C:\Program Files (x86)\Kakao\KakaoTalk\KakaoTalk.exe") -> None:

    _set_clipboard(text)
    _log.info("  [TEXT] 클립보드 준비 완료")

    hwnd = _find_kakao_chat_window(chat_name)
    if not hwnd:
        raise RuntimeError(f"'{chat_name}' 채팅창이 열려있지 않습니다.")
    root_hwnd = _user32.GetAncestor(hwnd, GA_ROOT) or hwnd
    _log.info(f"  [TEXT] 채팅창={hwnd}  root={root_hwnd}")

    _force_foreground(hwnd)

    edit = _find_input_richedit(hwnd)
    if not edit:
        raise RuntimeError("메시지 입력창을 찾지 못했습니다.")

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize",        ctypes.c_ulong),
            ("flags",         ctypes.c_ulong),
            ("hwndActive",    ctypes.c_void_p),
            ("hwndFocus",     ctypes.c_void_p),
            ("hwndCapture",   ctypes.c_void_p),
            ("hwndMenuOwner", ctypes.c_void_p),
            ("hwndMoveSize",  ctypes.c_void_p),
            ("hwndCaret",     ctypes.c_void_p),
            ("rcCaret",       ctypes.wintypes.RECT),
        ]
    gti = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
    tid_kakao, _ = win32process.GetWindowThreadProcessId(edit)
    _user32.GetGUIThreadInfo(tid_kakao, ctypes.byref(gti))
    _log.info(f"  [TEXT] 초기 포커스창={gti.hwndFocus}  RICHEDIT={edit}")

    edit_r  = win32gui.GetWindowRect(edit)
    cli_x   = (edit_r[2] - edit_r[0]) // 2
    cli_y   = (edit_r[3] - edit_r[1]) // 2
    lp_pos  = win32api.MAKELONG(cli_x, cli_y)
    win32api.PostMessage(edit, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp_pos)
    time.sleep(0.05)
    win32api.PostMessage(edit, win32con.WM_LBUTTONUP,   0,                   lp_pos)
    time.sleep(0.15)

    _user32.GetGUIThreadInfo(tid_kakao, ctypes.byref(gti))
    _log.info(f"  [TEXT] WM_LBUTTONDOWN 후 포커스창={gti.hwndFocus}  (RICHEDIT={edit})")

    EM_SETSEL        = 0x00B1
    WM_CLEAR         = 0x0303
    WM_PASTE         = 0x0302
    WM_GETTEXTLENGTH = 0x000E
    WM_GETTEXT       = 0x000D
    SCAN_RETURN      = 0x1C

    lp_dn   = (SCAN_RETURN << 16) | 1
    lp_up   = (1 << 31) | (1 << 30) | (SCAN_RETURN << 16) | 1

    def _paste() -> int:
        win32api.SendMessage(edit, EM_SETSEL, 0, -1)
        win32api.SendMessage(edit, WM_CLEAR, 0, 0)
        win32api.SendMessage(edit, WM_PASTE, 0, 0)
        time.sleep(0.5)
        n = win32api.SendMessage(edit, WM_GETTEXTLENGTH, 0, 0)
        _log.info(f"  [TEXT] WM_PASTE 완료: {n}자")
        return n

    def _len() -> int:
        return win32api.SendMessage(edit, WM_GETTEXTLENGTH, 0, 0)

    def _read50() -> str:
        buf = ctypes.create_unicode_buffer(52)
        ctypes.windll.user32.SendMessageW(edit, WM_GETTEXT, 52, buf)
        return repr(buf.value[:50])

    base = _paste()

    remaining = base
    for attempt in range(3):
        _log.info(f"  [TEXT] 전송 시도 #{attempt+1}")

        _force_foreground(hwnd)
        win32api.SendMessage(edit, win32con.WM_KEYDOWN, VK_RETURN, lp_dn)
        time.sleep(0.05)
        win32api.SendMessage(edit, win32con.WM_KEYUP,   VK_RETURN, lp_up)
        time.sleep(0.4)
        after_b = _len()
        if after_b != base:
            _log.info(f"  [TEXT]   B-prime: {after_b}자 ({after_b-base:+d}) → 재붙여넣기")
            base = _paste()
        else:
            _log.info(f"  [TEXT]   B-prime: {after_b}자 (+0)")

        _force_foreground(hwnd)
        win32api.PostMessage(root_hwnd, win32con.WM_KEYDOWN, VK_RETURN, lp_dn)
        win32api.PostMessage(root_hwnd, win32con.WM_KEYUP,   VK_RETURN, lp_up)
        time.sleep(0.6)
        remaining = _len()
        sent = remaining <= 10
        txt = _read50() if remaining <= 30 else ""
        _log.info(f"  [TEXT]   D(root): {remaining}자 ({remaining-base:+d}) "
                  f"{'✓' if sent else '✗'} {txt}")
        if sent:
            remaining = 0
            break
        if remaining != base:
            _log.info("  [TEXT]   내용 변경 → 재붙여넣기")
            base = _paste()

    _log.info(f"  [TEXT] '{chat_name}' 완료 (잔여={remaining}자)")
