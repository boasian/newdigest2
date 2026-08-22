#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KAOMI 오늘의 단신 2 — 채팅방 관리 및 전송 실행."""

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

BASE_DIR    = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
ICON_PATH   = str(BASE_DIR / "kaomi_news2.ico")
PYTHON_W    = Path(sys.executable).parent / "pythonw.exe"
PYTHON      = str(PYTHON_W) if PYTHON_W.exists() else sys.executable
MAIN_PY     = str(BASE_DIR / "main.py")
TASK_NAME   = "KAOMI뉴스단신2"

HDR_BG = "#125463"   # 틸 (단신 1의 네이비와 구분)


# ── 설정 ─────────────────────────────────────────────────────
def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)


def get_rooms(config: dict) -> list[str]:
    return list(config.get("kakao_pc", {}).get("chat_rooms", []))


def get_schedule(config: dict) -> tuple[int, int]:
    s = config.get("schedule", {})
    return s.get("hour", 6), s.get("minute", 0)


# ── 작업 스케줄러 ─────────────────────────────────────────────
def _run_ps(script: str) -> subprocess.CompletedProcess:
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".ps1")
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig") as f:
            f.write(script)
        return subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path],
            capture_output=True, text=True, encoding="utf-8",
        )
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def is_task_registered() -> bool:
    r = _run_ps(
        f'$t = Get-ScheduledTask -TaskName "{TASK_NAME}" -ErrorAction SilentlyContinue\n'
        f'if ($t) {{ exit 0 }} else {{ exit 1 }}'
    )
    return r.returncode == 0


def get_task_time() -> str:
    """등록된 작업의 실행 시각 문자열 반환 (예: '06:00'). 없으면 빈 문자열."""
    r = _run_ps(
        f'$t = Get-ScheduledTask -TaskName "{TASK_NAME}" -ErrorAction SilentlyContinue\n'
        f'if ($t) {{ $t.Triggers[0].StartBoundary }}'
    )
    if r.returncode != 0 or not r.stdout.strip():
        return ""
    # StartBoundary: "2024-01-01T06:00:00"
    try:
        t = r.stdout.strip().split("T")[1][:5]   # "06:00"
        return t
    except Exception:
        return ""


def register_task(hour: int, minute: int) -> None:
    time_str = f"{hour:02d}:{minute:02d}"
    script = f"""
$action  = New-ScheduledTaskAction -Execute '{PYTHON}' -Argument '"{MAIN_PY}"'
$trigger = New-ScheduledTaskTrigger -Daily -At {time_str}
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "{TASK_NAME}" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
"""
    r = _run_ps(script)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or r.stdout.strip())


def delete_task() -> None:
    r = _run_ps(f'Unregister-ScheduledTask -TaskName "{TASK_NAME}" -Confirm:$false')
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())


# ═══════════════════════════════════════════════════════════════
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KAOMI 오늘의 단신 2")
        self.resizable(False, False)
        try:
            self.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.config_data = load_config()
        self._checks: dict[str, tk.BooleanVar] = {}

        self._build()
        self._refresh_rooms()
        self._refresh_status()

        W, H = 400, 420
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

    # ── UI 구성 ───────────────────────────────────────────────
    def _build(self):
        # 헤더
        hdr = tk.Frame(self, bg=HDR_BG, height=46)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="KAOMI  오늘의 단신 2",
                 bg=HDR_BG, fg="white",
                 font=("맑은 고딕", 13, "bold")).pack(pady=10)

        body = tk.Frame(self, padx=18, pady=12)
        body.pack(fill="both", expand=True)

        # ── 채팅방 목록 ───────────────────────────────────────
        tk.Label(body, text="전송할 카카오톡 채팅방",
                 font=("맑은 고딕", 10, "bold")).pack(anchor="w")

        list_frame = tk.Frame(body, bd=1, relief="sunken")
        list_frame.pack(fill="x", pady=(4, 6))
        self._list_inner = tk.Frame(list_frame)
        self._list_inner.pack(fill="x", padx=6, pady=4)

        # ── 채팅방 추가 ───────────────────────────────────────
        add_frame = tk.Frame(body)
        add_frame.pack(fill="x", pady=(0, 10))
        self._new_room = tk.StringVar()
        entry = tk.Entry(add_frame, textvariable=self._new_room,
                         font=("맑은 고딕", 10))
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda e: self._add_room())
        tk.Button(add_frame, text="+ 추가", command=self._add_room,
                  bg=HDR_BG, fg="white", relief="flat",
                  font=("맑은 고딕", 9, "bold"), padx=10, pady=4,
                  cursor="hand2").pack(side="left", padx=(6, 0))

        # ── 즉시 전송 버튼 ────────────────────────────────────
        btn_row = tk.Frame(body)
        btn_row.pack(fill="x", pady=(0, 10))
        tk.Button(btn_row, text="지금 전송", command=self._send_now,
                  bg=HDR_BG, fg="white",
                  font=("맑은 고딕", 10, "bold"),
                  relief="flat", padx=16, pady=5,
                  cursor="hand2").pack(side="left")
        tk.Button(btn_row, text="취소", command=self.destroy,
                  font=("맑은 고딕", 10),
                  relief="flat", padx=16, pady=5,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(0, 10))

        # ── 자동 전송 시각 설정 ───────────────────────────────
        time_row = tk.Frame(body)
        time_row.pack(fill="x", pady=(0, 6))
        tk.Label(time_row, text="자동 전송 시각",
                 font=("맑은 고딕", 10, "bold")).pack(side="left")

        h, m = get_schedule(self.config_data)
        self._hour = tk.StringVar(value=f"{h:02d}")
        self._min  = tk.StringVar(value=f"{m:02d}")

        tk.Spinbox(time_row, from_=0, to=23, width=3, format="%02.0f",
                   textvariable=self._hour,
                   font=("맑은 고딕", 11)).pack(side="left", padx=(10, 2))
        tk.Label(time_row, text="시", font=("맑은 고딕", 10)).pack(side="left")
        tk.Spinbox(time_row, from_=0, to=59, width=3, format="%02.0f",
                   textvariable=self._min,
                   font=("맑은 고딕", 11)).pack(side="left", padx=(6, 2))
        tk.Label(time_row, text="분", font=("맑은 고딕", 10)).pack(side="left")

        # ── 자동 전송 상태 ────────────────────────────────────
        self._status_var = tk.StringVar()
        self._status_lbl = tk.Label(body, textvariable=self._status_var,
                                    font=("맑은 고딕", 10))
        self._status_lbl.pack(anchor="w", pady=(0, 6))

        auto_row = tk.Frame(body)
        auto_row.pack(fill="x")
        tk.Button(auto_row, text="자동 전송 시작",
                  command=self._auto_start,
                  bg="#1a6e1a", fg="white",
                  font=("맑은 고딕", 10, "bold"),
                  relief="flat", padx=12, pady=5,
                  cursor="hand2").pack(side="left")
        tk.Button(auto_row, text="자동 전송 중지",
                  command=self._auto_stop,
                  bg="#8b1a1a", fg="white",
                  font=("맑은 고딕", 10),
                  relief="flat", padx=12, pady=5,
                  cursor="hand2").pack(side="left", padx=(8, 0))

        self.bind("<Escape>", lambda e: self.destroy())

    # ── 채팅방 목록 렌더링 ────────────────────────────────────
    def _refresh_rooms(self):
        for w in self._list_inner.winfo_children():
            w.destroy()

        rooms = get_rooms(self.config_data)
        if not rooms:
            tk.Label(self._list_inner, text="채팅방을 추가하세요",
                     fg="#aaa", font=("맑은 고딕", 9)).pack(anchor="w")
            return

        self._checks = {}
        for room in rooms:
            row = tk.Frame(self._list_inner)
            row.pack(fill="x", pady=1)
            var = tk.BooleanVar(value=True)
            self._checks[room] = var
            tk.Checkbutton(row, text=room, variable=var,
                           font=("맑은 고딕", 10), anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(row, text="삭제",
                      command=lambda r=room: self._remove_room(r),
                      relief="flat", fg="#c00", font=("맑은 고딕", 9),
                      cursor="hand2").pack(side="right")

    def _add_room(self):
        name = self._new_room.get().strip()
        if not name:
            return
        rooms = get_rooms(self.config_data)
        if name in rooms:
            messagebox.showinfo("알림", f"「{name}」은 이미 목록에 있습니다.", parent=self)
            return
        rooms.append(name)
        self.config_data["kakao_pc"]["chat_rooms"] = rooms
        save_config(self.config_data)
        self._new_room.set("")
        self._refresh_rooms()

    def _remove_room(self, name: str):
        if not messagebox.askyesno("삭제 확인", f"「{name}」을 목록에서 삭제할까요?", parent=self):
            return
        rooms = [r for r in get_rooms(self.config_data) if r != name]
        self.config_data["kakao_pc"]["chat_rooms"] = rooms
        save_config(self.config_data)
        self._refresh_rooms()

    # ── 즉시 전송 ─────────────────────────────────────────────
    def _send_now(self):
        selected = [r for r, v in self._checks.items() if v.get()]
        if not selected:
            messagebox.showwarning("선택 오류", "전송할 채팅방을 하나 이상 선택하세요.", parent=self)
            return
        original = get_rooms(self.config_data)
        self.config_data["kakao_pc"]["chat_rooms"] = selected
        save_config(self.config_data)
        self.destroy()
        subprocess.Popen([sys.executable, MAIN_PY])
        self.config_data["kakao_pc"]["chat_rooms"] = original
        save_config(self.config_data)

    # ── 자동 전송 ─────────────────────────────────────────────
    def _get_time_input(self) -> tuple[int, int] | None:
        try:
            h = int(self._hour.get())
            m = int(self._min.get())
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            return h, m
        except ValueError:
            messagebox.showwarning("입력 오류", "올바른 시각을 입력하세요 (0~23시, 0~59분).", parent=self)
            return None

    def _refresh_status(self):
        if is_task_registered():
            t = get_task_time()
            label = f"매일 {t}" if t else "매일"
            self._status_var.set(f"● {label} 자동 전송 중")
            self._status_lbl.config(fg="#1a8a1a")
        else:
            self._status_var.set("○ 자동 전송 꺼짐")
            self._status_lbl.config(fg="#888")

    def _auto_start(self):
        rooms = get_rooms(self.config_data)
        if not rooms:
            messagebox.showwarning("설정 오류", "채팅방을 먼저 추가하세요.", parent=self)
            return
        t = self._get_time_input()
        if t is None:
            return
        h, m = t
        # 시각을 config에 저장
        self.config_data["schedule"] = {"hour": h, "minute": m}
        save_config(self.config_data)
        try:
            register_task(h, m)
            messagebox.showinfo(
                "자동 전송 등록",
                f"매일 {h:02d}:{m:02d}에 아래 채팅방으로 자동 전송됩니다.\n\n"
                + "\n".join(f"· {r}" for r in rooms),
                parent=self,
            )
            self._refresh_status()
        except Exception as e:
            messagebox.showerror("오류", f"등록 실패:\n{e}", parent=self)

    def _auto_stop(self):
        if not is_task_registered():
            messagebox.showinfo("알림", "등록된 자동 전송이 없습니다.", parent=self)
            return
        if messagebox.askyesno("자동 전송 중지", "매일 자동 전송을 중지하시겠습니까?", parent=self):
            try:
                delete_task()
                self._refresh_status()
            except Exception as e:
                messagebox.showerror("오류", f"중지 실패:\n{e}", parent=self)


if __name__ == "__main__":
    App().mainloop()
