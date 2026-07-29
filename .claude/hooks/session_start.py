"""SessionStart hook: 输出项目上下文为 system reminder"""
import json, sys, pathlib

PROJECT = pathlib.Path(r"D:\就业学习资料包251116\秋招AI产品项目\address-audit-agent")
MEMORY = pathlib.Path(r"C:\Users\张逸帆\.claude\projects\D---------251116---AI----\memory")

lines = ["## 项目上下文（自动加载）", ""]

# 读取 Memory
for name in ["MEMORY.md", "project-address-audit-agent.md"]:
    f = MEMORY / name
    if f.exists():
        lines.append(f.read_text(encoding="utf-8"))

# 读取 SPEC.md 最近变更
spec = PROJECT / "SPEC.md"
if spec.exists():
    content = spec.read_text(encoding="utf-8")
    # 提取最近两次变更
    sections = content.split("## 20")
    recent = sections[:3] if len(sections) > 3 else sections
    lines.append("\n## 最近变更 (SPEC.md)")
    lines.append("\n".join(recent))

output = "\n".join(lines)[:3000]  # cap
print(json.dumps({"systemMessage": f"项目上下文已加载（{len(output)} 字符）",
                  "hookSpecificOutput": {"hookEventName": "SessionStart",
                                         "additionalContext": output}}))
