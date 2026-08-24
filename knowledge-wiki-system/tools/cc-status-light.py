"""
Claude Code Task Status Light
==============================
桌面悬浮指示灯，最多 6 盏，按时间排列最近任务。

灯色含义（按用户需要关注的程度）：
  🟢 绿灯：无需关注 — CC 正在执行 / 已完成
  🟡 黄灯：需要你操作 — CC 等你授权、输入、确认
  🔴 红灯：需要你回头处理 — 任务失败 / 被跳过

数据源：~/.claude/task_lights.json（由 Claude 实时更新）
"""

import json
import sys
import time
import threading
import subprocess
import winsound
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLAUDE_DIR = Path.home() / ".claude"
SESSIONS_DIR = CLAUDE_DIR / "sessions"
TASK_STATE_FILE = CLAUDE_DIR / "task_lights.json"
POLL_INTERVAL = 1.0
MAX_LIGHTS = 6

COLORS = {
    "green":  "#22c55e",
    "yellow": "#eab308",
    "red":    "#ef4444",
    "gray":   "#6b7280",
}
RIMS = {
    "green":  "#16a34a",
    "yellow": "#ca8a04",
    "red":    "#dc2626",
    "gray":   "#4b5563",
}

LIGHT_R = 11
CARD_W = 72
CARD_H = 72
PAD_X = 10
PAD_Y = 8
ALPHA = 0.88


def _pid_alive(pid):
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, timeout=3)
        return str(pid) in r.stdout and "claude" in r.stdout.lower()
    except Exception:
        return False


def cc_state():
    """返回 (alive, busy)"""
    if not SESSIONS_DIR.exists():
        return False, False
    alive, busy = False, False
    for f in SESSIONS_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            pid = d.get("pid")
            if pid and _pid_alive(pid):
                alive = True
                if d.get("status") == "busy":
                    busy = True
        except Exception:
            continue
    return alive, busy


def load_tasks():
    if TASK_STATE_FILE.exists():
        try:
            tasks = json.loads(TASK_STATE_FILE.read_text(encoding="utf-8"))
            # 按 id 排序，只取最近 MAX_LIGHTS 个
            tasks.sort(key=lambda t: int(t.get("id", "0")))
            return tasks[-MAX_LIGHTS:]
        except Exception:
            pass
    return []


def task_light(status, cc_alive, cc_busy):
    """
      completed                    → green
      in_progress + cc busy        → green  (CC 在干活，不用管)
      in_progress + cc idle/alive  → yellow (CC 在等你操作)
      in_progress + cc dead        → red
      pending / failed             → red    (还没做或失败了，需要你回头处理)
    """
    if status == "completed":
        return "green"
    if status == "in_progress":
        if not cc_alive:
            return "red"
        return "green" if cc_busy else "yellow"
    # pending, failed, 其他 → 都是红灯
    return "red"


class TaskLightBoard:

    def __init__(self):
        import tkinter as tk
        self.tk = tk
        self.root = tk.Tk()
        self.root.title("CC")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", ALPHA)

        self.canvas = tk.Canvas(self.root, bg="#16161a", highlightthickness=0)
        self.canvas.pack()
        self._w = self._h = 100
        self._last_hash = ""

        self.canvas.bind("<Button-1>", lambda e: self._drag_start(e))
        self.canvas.bind("<B1-Motion>", lambda e: self._drag_move(e))
        self.canvas.bind("<Button-3>", lambda e: self._quit())

        self.running = True
        threading.Thread(target=self._poll, daemon=True).start()

    def _drag_start(self, e):
        self._dx, self._dy = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self._dx
        y = self.root.winfo_y() + e.y - self._dy
        self.root.geometry(f"+{x}+{y}")

    def _quit(self):
        self.running = False
        self.root.destroy()

    def _resize(self, n):
        n = max(n, 1)
        self._w = PAD_X * 2 + n * CARD_W
        self._h = PAD_Y * 2 + CARD_H + 14
        self.canvas.config(width=self._w, height=self._h)
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{self._w}x{self._h}+{sw - self._w - 16}+{60}")

    def _round_rect(self, x1, y1, x2, y2, r):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True)

    def _draw(self, items):
        c = self.canvas
        c.delete("all")
        w, h = self._w, self._h

        # 圆角背景
        bg_id = self._round_rect(1, 1, w - 1, h - 1, 10)
        c.itemconfig(bg_id, fill="#16161a", outline="#2a2a30", width=1)

        for i, item in enumerate(items):
            cx = PAD_X + CARD_W // 2 + i * CARD_W
            cy = PAD_Y + LIGHT_R + 4
            color = item["light_color"]

            rr = LIGHT_R
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr,
                          fill=COLORS[color], outline=RIMS[color], width=2)

            short = item.get("label", item["subject"])
            if len(short) > 8:
                short = short[:7] + "…"
            c.create_text(cx, cy + LIGHT_R + 12, text=short,
                          fill="#d4d4d8", font=("Microsoft YaHei UI", 9))

            ico = {"green": "v", "yellow": "~", "red": "x", "gray": "o"}.get(color, "?")
            c.create_text(cx, cy + LIGHT_R + 28, text=ico,
                          fill=COLORS[color], font=("Segoe UI", 9, "bold"))

        if items:
            st = items[0].get("cc_state", "")
            c.create_text(w // 2, h - 8, text=st, fill="#555555",
                          font=("Microsoft YaHei UI", 7))

    def _poll(self):
        prev_colors = {}  # subject → color，用于检测颜色变化
        while self.running:
            try:
                cc_alive, cc_busy = cc_state()
                tasks = load_tasks()
                items = []

                for t in tasks:
                    color = task_light(t["status"], cc_alive, cc_busy)
                    items.append({
                        "subject": t["subject"],
                        "label": t["subject"],
                        "light_color": color,
                    })
                    # 检测颜色变化：变黄或变红时播放提示音
                    subj = t["subject"]
                    prev = prev_colors.get(subj)
                    if prev is not None and prev != color and color in ("yellow", "red"):
                        self._beep(color)
                    prev_colors[subj] = color

                if not items:
                    items.append({
                        "subject": "CC", "label": "CC",
                        "light_color": "green" if cc_busy else ("yellow" if cc_alive else "gray"),
                    })

                st = "CC: Busy" if cc_busy else ("CC: Idle" if cc_alive else "CC: Offline")
                for it in items:
                    it["cc_state"] = st

                h = json.dumps([(i["subject"], i["light_color"]) for i in items], sort_keys=True)
                if h != self._last_hash:
                    self._last_hash = h
                    self.root.after(0, self._resize, len(items))
                    self.root.after(10, self._draw, items)
            except Exception:
                pass
            time.sleep(POLL_INTERVAL)

    def _beep(self, color):
        """播放提示音：黄灯叮，红灯嗡"""
        try:
            if color == "yellow":
                winsound.Beep(1000, 300)  # 高音
            else:  # red
                winsound.Beep(500, 200)
                time.sleep(0.08)
                winsound.Beep(500, 200)
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def main():
    TaskLightBoard().run()


if __name__ == "__main__":
    main()
