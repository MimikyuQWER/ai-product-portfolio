"""
双工具转换对比脚本
对每个 PDF/PPTX 同时用 MarkItDown 和 pdfplumber 转换，保留质量更好的版本。
"""
import sys, re
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from markitdown import MarkItDown
import pdfplumber

SOURCE = Path(r"D:\就业学习资料包251116\金融相关\上农商资管材料")
RAW = Path.home() / "knowledge-wiki" / "raw" / "上农商资管材料"

md = MarkItDown()


def quality_score(text: str) -> tuple[int, str]:
    """给文本打分：越高越好。返回 (分数, 诊断)"""
    score = 100
    issues = []

    # 1. 颜色值污染（RGB数字组）
    color_pattern = re.findall(r'\b\d{1,3},\d{1,3},\d{1,3}\b', text)
    color_count = len(color_pattern)
    if color_count > 100:
        score -= 40
        issues.append(f"颜色值{color_count}个")
    elif color_count > 10:
        score -= 15
        issues.append(f"颜色值{color_count}个")

    # 2. 破碎的markdown表格（空单元格）
    empty_cells = len(re.findall(r'\|\s*\|', text))
    if empty_cells > 200:
        score -= 30
        issues.append(f"空表格{empty_cells}个")
    elif empty_cells > 50:
        score -= 10

    # 3. 连续空行过多
    blank_blocks = len(re.findall(r'\n{4,}', text))
    if blank_blocks > 30:
        score -= 10
        issues.append(f"大段空白{blank_blocks}处")

    # 4. 纯数字行（图表散落数据）
    number_lines = len(re.findall(r'^\s*[\d\s\.%]+\s*$', text, re.MULTILINE))
    if number_lines > 100:
        score -= 15
        issues.append(f"数字碎片{number_lines}行")

    # 5. 有效文本密度
    total_chars = len(text)
    if total_chars < 500:
        score -= 30
        issues.append("文本过短")
    elif total_chars < 2000:
        score -= 10

    return max(score, 0), "; ".join(issues) if issues else "干净"


def convert_markitdown(src: Path) -> str | None:
    """MarkItDown 转换"""
    try:
        result = md.convert(str(src))
        return result.text_content
    except Exception as e:
        return None


def convert_pdfplumber(src: Path) -> str | None:
    """pdfplumber 转换（仅PDF）"""
    if src.suffix.lower() != ".pdf":
        return None
    try:
        lines = [f"# {src.stem}\n\n原始: {src.name}\n"]
        with pdfplumber.open(str(src)) as doc:
            for i, page in enumerate(doc.pages, 1):
                text = page.extract_text()
                if text:
                    lines.append(f"## 第{i}页\n\n{text}\n")
        return "\n".join(lines)
    except Exception as e:
        return None


def process_file(src: Path):
    """对单个文件跑两种工具，选优"""
    suffix = src.suffix.lower()

    if suffix == ".zip":
        return  # 跳过zip

    if suffix not in (".pdf", ".pptx", ".ppt"):
        return

    # 确定目标目录
    rel = src.relative_to(SOURCE)
    dst_dir = RAW / rel.parent
    dst_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📄 {src.name}")

    results = {}

    # 方案A: MarkItDown
    text_a = convert_markitdown(src)
    if text_a:
        score_a, diag_a = quality_score(text_a)
        results["MarkItDown"] = (score_a, diag_a, text_a)

    # 方案B: pdfplumber (仅PDF)
    if suffix == ".pdf":
        text_b = convert_pdfplumber(src)
        if text_b:
            score_b, diag_b = quality_score(text_b)
            results["pdfplumber"] = (score_b, diag_b, text_b)

    if not results:
        print(f"  ❌ 两种工具都失败")
        return

    # 选优
    best = max(results.items(), key=lambda x: x[1][0])
    name, (score, diag, text) = best

    # 保存
    dst = dst_dir / f"{src.stem}.md"
    dst.write_text(text, encoding="utf-8")

    # 报告
    for tool, (s, d, _) in results.items():
        winner = "⭐" if tool == name else "  "
        print(f"  {winner} {tool}: 得分{s} — {d}")

    # 如果两者都有但选了MarkItDown，说明pdfplumber失败/更差，也保存pdfplumber版本到_v2子目录供参考
    if len(results) == 2:
        loser = [k for k in results if k != name][0]
        loser_score = results[loser][0]
        if loser_score < score - 20:
            print(f"  💡 {name} 明显优于 {loser} (差{score - loser_score}分)")


def main():
    print("=" * 50)
    print("双工具转换对比")
    print(f"源: {SOURCE}")
    print(f"目标: {RAW}")
    print("=" * 50)

    for item in sorted(SOURCE.rglob("*")):
        if item.is_file():
            process_file(item)

    print(f"\n完成，输出: {RAW}")


if __name__ == "__main__":
    main()
