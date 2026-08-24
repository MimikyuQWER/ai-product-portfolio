"""
批量素材转换脚本
用 MarkItDown 将 PDF/PPTX 转为 Markdown，存入 raw/ 目录。
"""
import sys, os, zipfile, shutil
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from markitdown import MarkItDown

SOURCE = Path(r"D:\就业学习资料包251116\金融相关\上农商资管材料")
RAW = Path.home() / "knowledge-wiki" / "raw" / "上农商资管材料"

md = MarkItDown()
TOTAL = {"ok": 0, "fail": 0, "skip": 0}


def convert_file(src: Path, dst_dir: Path):
    """转换单个文件为同名 .md"""
    stem = src.stem
    # 跳过 zip 和非目标格式
    if src.suffix.lower() == ".zip":
        return
    if src.suffix.lower() not in (".pdf", ".pptx", ".ppt"):
        print(f"  ⏭️ 跳过: {src.name}")
        TOTAL["skip"] += 1
        return

    dst = dst_dir / f"{stem}.md"
    dst_dir.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        print(f"  ⏭️ 已存在: {stem}.md")
        TOTAL["skip"] += 1
        return

    try:
        result = md.convert(str(src))
        dst.write_text(result.text_content, encoding="utf-8")
        print(f"  ✅ {stem}.md")
        TOTAL["ok"] += 1
    except Exception as e:
        print(f"  ❌ {src.name}: {e}")
        TOTAL["fail"] += 1


def process_dir(src_dir: Path, dst_dir: Path):
    """递归处理目录"""
    for item in sorted(src_dir.iterdir()):
        if item.is_dir():
            process_dir(item, dst_dir / item.name)
        elif item.suffix.lower() == ".zip":
            # 解压到临时目录再处理
            tmp = src_dir / "_unzipped" / item.stem
            if not tmp.exists():
                print(f"\n📦 解压: {item.name}")
                with zipfile.ZipFile(item, 'r') as z:
                    z.extractall(tmp)
            process_dir(tmp, dst_dir / item.stem)
        else:
            convert_file(item, dst_dir)


def main():
    print("=" * 50)
    print("素材转换入库")
    print(f"源目录: {SOURCE}")
    print(f"目标:   {RAW}")
    print("=" * 50)

    process_dir(SOURCE, RAW)

    print(f"\n{'=' * 50}")
    print(f"完成: ✅ {TOTAL['ok']} | ❌ {TOTAL['fail']} | ⏭️ {TOTAL['skip']}")
    print(f"输出路径: {RAW}")


if __name__ == "__main__":
    main()
