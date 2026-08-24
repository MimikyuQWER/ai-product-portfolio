"""
单文件合并：AI版 + Full版 → entities/xxx.md（带大纲索引）
"""
import sys, re, shutil
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ENTITIES = Path.home() / "knowledge-wiki" / "entities"
FULL = Path.home() / "knowledge-wiki" / "full" / "entities"
OBSERVATIONS = Path.home() / "knowledge-wiki" / "observations"
PATTERNS = Path.home() / "knowledge-wiki" / "patterns"

def extract_body(text: str) -> str:
    """提取frontmatter之后的正文"""
    if text.startswith('---'):
        parts = text.split('---', 2)
        return parts[2] if len(parts) > 2 else text
    return text

def extract_frontmatter(text: str) -> str:
    """提取frontmatter"""
    if text.startswith('---'):
        parts = text.split('---', 2)
        return '---' + parts[1] + '---' if len(parts) > 2 else ''
    return ''

def gen_outline(text: str) -> str:
    """从headings生成大纲索引"""
    body = extract_body(text)
    headings = re.findall(r'^## (.+)$', body, re.MULTILINE)

    lines = ["## 大纲索引\n"]
    for h in headings:
        h_clean = h.strip()
        # 跳过深层导航和标签等元信息
        if h_clean in ['深层导航', '标签', '大纲索引', '关联', '🏷️ 相关', '🏷️ 标签']:
            continue
        # 用缩进表示层级
        lines.append(f"- {h_clean}")
    lines.append("")
    return "\n".join(lines)

def merge_files(ai_file: Path, full_file: Path):
    """合并AI版和Full版"""
    ai_text = ai_file.read_text(encoding='utf-8')
    full_text = full_file.read_text(encoding='utf-8')

    fm = extract_frontmatter(ai_text)
    ai_body = extract_body(ai_text)
    full_body = extract_body(full_text)

    # 去重：找出full版中AI版没有的section
    ai_headings = set(re.findall(r'^## (.+)$', ai_body, re.MULTILINE))
    full_sections = re.split(r'\n(?=## )', full_body)

    unique_sections = []
    for section in full_sections:
        h_match = re.match(r'^## (.+)', section)
        if h_match:
            h_name = h_match.group(1).strip()
            # 跳过关联、导航、标签类section
            if any(skip in h_name for skip in ['关联', 'AI精简版', '标签', '🏷️']):
                continue
            if h_name not in ai_headings:
                unique_sections.append(section)

    # 更新AI版中的full/链接为raw/
    ai_body = re.sub(r'\[\[full/entities/([^\]|]+)(?:\|[^\]]+)?\]\]', r'[raw/\1]', ai_body)
    ai_body = re.sub(r'📖 \*\*完整版\*\* → .*?\n', '', ai_body)

    # 如果已有大纲索引，替换；否则在TL;DR后插入
    outline = gen_outline(ai_text)

    if '## 大纲索引' in ai_body:
        ai_body = re.sub(r'## 大纲索引.*?(?=\n## )', outline.strip(), ai_body, flags=re.DOTALL)
    else:
        # 在TL;DR后、第一个section前插入
        ai_body = re.sub(r'(> 🎯[^\n]*\n)', r'\1\n' + outline + '\n', ai_body, count=1)

    # 如果full版有独特内容，追加到AI版末尾(深层导航之前)
    if unique_sections:
        # 在"深层导航"或"标签"前插入
        insert_point = None
        for pattern in [r'\n## 🔗 深层导航', r'\n## 🏷️ 标签', r'\n## 🏷️ 相关']:
            m = re.search(pattern, ai_body)
            if m:
                insert_point = m.start()
                break

        extra = "\n## 补充详细内容（来自原full版）\n\n" + "\n".join(unique_sections)
        # 清理残留的full/链接
        extra = re.sub(r'\[\[\.\./entities/([^\]|]+)(?:\|[^\]]+)?\]\]', r'[[\1]]', extra)

        if insert_point:
            ai_body = ai_body[:insert_point] + extra + "\n" + ai_body[insert_point:]
        else:
            ai_body += extra

    merged = fm + '\n' + ai_body
    ai_file.write_text(merged, encoding='utf-8')

    return len(ai_text), len(full_text), len(merged)

# ===== 主流程 =====
pairs = []
for f in sorted(ENTITIES.glob('*.md')):
    full = FULL / f.name
    if full.exists():
        pairs.append((f, full))

total_ai = total_full = total_merged = 0
print(f"合并 {len(pairs)} 对页面...\n")

for ai, full in pairs:
    try:
        ai_len, full_len, merged_len = merge_files(ai, full)
        total_ai += ai_len
        total_full += full_len
        total_merged += merged_len
        delta = merged_len - ai_len
        print(f"  ✅ {ai.name}: AI版{ai_len//28}行 + Full{full_len//28}行 → 合并{merged_len//28}行 ({delta//28:+d})")
    except Exception as e:
        print(f"  ❌ {ai.name}: {e}")

print(f"\n总计: {total_ai//28}行 + {total_full//28}行 → {total_merged//28}行")

# 删除 full/ 目录
full_root = FULL.parent
if full_root.exists():
    shutil.rmtree(str(full_root))
    print(f"\n已删除 full/ 目录")

# 更新 patterns/ 和 observations/ 下的 full/ 链接
for d in [PATTERNS, OBSERVATIONS]:
    for f in d.glob('*.md'):
        if f.name == '.gitkeep':
            continue
        text = f.read_text(encoding='utf-8')
        text = re.sub(r'\[\[full/[^\]]+\]\]', '', text)
        text = re.sub(r'\[\[\.\./full/[^\]]+\]\]', '', text)
        f.write_text(text, encoding='utf-8')

print("patterns/ 和 observations/ 链接已清理")
