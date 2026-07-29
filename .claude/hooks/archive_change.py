"""PostToolUse hook: 代码变更自动追加到 ARCHIVE.md"""
import json, sys, pathlib, datetime

PROJECT = pathlib.Path(r"D:\就业学习资料包251116\秋招AI产品项目\address-audit-agent")

try:
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # 只追踪项目核心文件
    tracked = ["agent/", "app.py", "prompt.txt", "landing.html"]
    if not any(file_path.replace("\\", "/").startswith(t) or file_path.endswith(t) for t in tracked):
        sys.exit(0)

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    archive = PROJECT / "ARCHIVE.md"
    entry = f"| {ts} | {tool} | {file_path} |\n"

    if not archive.exists():
        archive.write_text("# 变更归档\n\n| 时间 | 操作 | 文件 |\n|---|---|---|\n", encoding="utf-8")

    with open(archive, "a", encoding="utf-8") as f:
        f.write(entry)
except Exception:
    pass  # hook 静默失败，不阻塞正常操作
