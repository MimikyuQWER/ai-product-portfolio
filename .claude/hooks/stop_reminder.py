"""Stop hook: 检查未提交变更，提醒更新 SPEC.md/commit/wiki"""
import json, subprocess, pathlib

PROJECT = pathlib.Path(r"D:\就业学习资料包251116\秋招AI产品项目\address-audit-agent")
WIKI = pathlib.Path(r"C:\Users\张逸帆\knowledge-wiki")

reminders = []

try:
    r = subprocess.run(["git", "status", "--short"], cwd=str(PROJECT),
                       capture_output=True, text=True, timeout=5)
    if r.stdout.strip():
        changed = [l for l in r.stdout.split("\n") if l.strip() and not l.startswith("__pycache__")]
        if changed:
            reminders.append(f"项目有未提交文件，请更新 SPEC.md 后 commit")
except Exception:
    pass

try:
    r = subprocess.run(["git", "status", "--short"], cwd=str(WIKI),
                       capture_output=True, text=True, timeout=5)
    if r.stdout.strip():
        reminders.append("Wiki 有未提交变更，请 commit")
except Exception:
    pass

if reminders:
    print(json.dumps({"systemMessage": " | ".join(reminders)}, ensure_ascii=False))
