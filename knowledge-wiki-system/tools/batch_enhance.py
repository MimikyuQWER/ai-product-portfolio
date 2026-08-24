"""
全量增强raw提取：文本+表格+图片标记，带进度条。
"""
import sys, pdfplumber
from pathlib import Path
from markitdown import MarkItDown

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SOURCE = Path(r"D:\就业学习资料包251116\金融相关\上农商资管材料")
RAW = Path.home() / "knowledge-wiki" / "raw" / "上农商资管材料"
md = MarkItDown()


def process_pdf(src: Path, dst_dir: Path) -> dict:
    """增强PDF提取：文本+表格+图片"""
    dst = dst_dir / f"{src.stem}.md"
    dst_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"# {src.stem}\n\n原始: {src.name}\n"]
    total_tables = 0
    total_images = 0

    with pdfplumber.open(str(src)) as doc:
        for i, page in enumerate(doc.pages, 1):
            lines.append(f"## 第{i}页\n")
            text = page.extract_text()
            if text:
                lines.append(text + "\n")

            tables = page.extract_tables()
            for j, table in enumerate(tables):
                if table and any(any(cell and str(cell).strip() for cell in row) for row in table):
                    header = table[0]
                    lines.append(f"### 📊 表格{i}.{j+1}\n")
                    if header:
                        clean_header = [str(c).replace('\n',' ') if c else '' for c in header]
                        lines.append('| ' + ' | '.join(clean_header) + ' |')
                        lines.append('|' + '|'.join(['---' for _ in header]) + '|')
                        for row in table[1:]:
                            clean_row = [str(c).replace('\n',' ') if c else '' for c in row]
                            lines.append('| ' + ' | '.join(clean_row) + ' |')
                    lines.append('')
                    total_tables += 1

            for k, img in enumerate(page.images):
                lines.append(f'![图表{i}_{k+1}](图表/{src.stem}_p{i}_{k+1}.png)\n')
                total_images += 1

    content = f"# {src.stem}\n\n原始PDF: {src.name}\n页数: {len(doc.pages)}\n表格: {total_tables}个\n图片: {total_images}个\n\n" + "\n".join(lines)
    dst.write_text(content, encoding="utf-8")
    return {"name": src.name, "pages": len(doc.pages), "tables": total_tables, "images": total_images, "size": len(content)}


def process_pptx(src: Path, dst_dir: Path) -> dict:
    """PPTX用MarkItDown转换"""
    dst = dst_dir / f"{src.stem}.md"
    dst_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = md.convert(str(src))
        dst.write_text(result.text_content, encoding="utf-8")
        return {"name": src.name, "pages": 0, "tables": 0, "images": 0, "size": len(result.text_content)}
    except Exception:
        return None


def main():
    files = []
    for item in sorted(SOURCE.rglob("*")):
        if item.is_file() and item.suffix.lower() in (".pdf", ".pptx", ".ppt"):
            files.append(item)

    total = len(files)
    print(f"共 {total} 个文件\n")

    results = []
    for idx, f in enumerate(files, 1):
        rel = f.relative_to(SOURCE)
        dst_dir = RAW / rel.parent

        bar = "█" * (idx * 20 // total) + "░" * (20 - idx * 20 // total)
        print(f"[{bar}] {idx}/{total} {f.name[:60]}...", end=" ", flush=True)

        try:
            if f.suffix.lower() == ".pdf":
                r = process_pdf(f, dst_dir)
            else:
                r = process_pptx(f, dst_dir)

            if r:
                r["idx"] = idx
                results.append(r)
                print(f"✅ {r.get('pages',0)}页 {r.get('tables',0)}表 {r['size']//1024}KB")
            else:
                print("❌ 失败")
        except Exception as e:
            print(f"❌ {str(e)[:80]}")

    print(f"\n{'='*50}")
    total_t = sum(r.get('tables',0) for r in results)
    total_img = sum(r.get('images',0) for r in results)
    total_size = sum(r['size'] for r in results)
    print(f"完成: {len(results)}/{total} 文件, {total_t}表格, {total_img}图片, {total_size//1024}KB")
    print(f"输出: {RAW}")


if __name__ == "__main__":
    main()
