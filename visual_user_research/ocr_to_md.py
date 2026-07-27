"""
OCR the 29-page rendered PDF and produce a clean Markdown file.
Usage: python ocr_to_md.py
"""
import os
import sys
from pathlib import Path
import pytesseract
from PIL import Image

# --- Config ---
WORK_DIR = Path(__file__).resolve().parent
IMAGE_DIR = WORK_DIR / "pdf_pages"
OUTPUT_MD = WORK_DIR / "虚拟人迭代文档.md"

# Auto-detect or manually set tesseract path
POSSIBLE_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\张逸帆\AppData\Local\Tesseract-OCR\tesseract.exe",
    r"C:\Tesseract-OCR\tesseract.exe",
]


def find_tesseract() -> str:
    """Find tesseract executable, trying PATH first then common locations."""
    # Try PATH
    import shutil
    path_tess = shutil.which("tesseract")
    if path_tess:
        print(f"[OK] Found tesseract in PATH: {path_tess}")
        return path_tess

    # Try common install locations
    for p in POSSIBLE_TESSERACT_PATHS:
        if os.path.exists(p):
            print(f"[OK] Found tesseract: {p}")
            return p

    print("[ERROR] Tesseract not found!")
    print("  Checked:")
    for p in POSSIBLE_TESSERACT_PATHS:
        print(f"    {p} -> {'EXISTS' if os.path.exists(p) else 'MISSING'}")
    print("\n  Install tesseract from: https://github.com/UB-Mannheim/tesseract/releases")
    sys.exit(1)


def ensure_chinese_lang(tesseract_path: str) -> bool:
    """Check if chi_sim traineddata is available."""
    tess_dir = Path(tesseract_path).parent / "tessdata"
    chi_sim = tess_dir / "chi_sim.traineddata"
    if chi_sim.exists():
        print(f"[OK] Chinese language data: {chi_sim}")
        return True

    # Check if it's in TESSDATA_PREFIX
    env_tessdata = os.environ.get("TESSDATA_PREFIX", "")
    if env_tessdata:
        chi_sim_env = Path(env_tessdata) / "chi_sim.traineddata"
        if chi_sim_env.exists():
            return True

    print(f"[WARN] chi_sim.traineddata not found at {tess_dir}")
    print("  Downloading from GitHub...")
    import urllib.request
    url = "https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata"
    try:
        os.makedirs(tess_dir, exist_ok=True)
        urllib.request.urlretrieve(url, str(chi_sim))
        print(f"[OK] Downloaded chi_sim.traineddata ({chi_sim.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download: {e}")
        return False


def ocr_pages(tesseract_path: str) -> list[tuple[int, str]]:
    """OCR all rendered pages. Returns list of (page_number, text)."""
    page_files = sorted(IMAGE_DIR.glob("page_*.png"))
    if not page_files:
        print(f"[ERROR] No page images found in {IMAGE_DIR}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"OCR Processing {len(page_files)} pages...")
    print(f"{'='*60}")

    results = []
    for i, pf in enumerate(page_files):
        page_num = i + 1
        img = Image.open(pf)
        w, h = img.size
        print(f"  [{page_num:2d}/{len(page_files)}] {pf.name} ({w}x{h}) ...", end=" ", flush=True)

        try:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng")
            char_count = len(text.strip())
            results.append((page_num, text))
            print(f"{char_count:,} chars extracted")
        except Exception as e:
            print(f"ERROR: {e}")
            results.append((page_num, f"[OCR ERROR: {e}]"))

    return results


def clean_ocr_text(text: str) -> str:
    """Basic cleaning of OCR output."""
    # Remove excessive blank lines (keep max 2 consecutive)
    lines = text.split('\n')
    cleaned = []
    blank_count = 0
    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                cleaned.append('')
        else:
            blank_count = 0
            cleaned.append(line)
    return '\n'.join(cleaned)


def build_markdown(pages: list[tuple[int, str]]) -> str:
    """Build clean Markdown from OCR results."""
    md_lines = [
        "# 虚拟数字人产品迭代文档",
        "",
        "> 从 PDF 自动提取 · 29页 · OCR识别",
        "",
        "---",
        "",
    ]

    for page_num, raw_text in pages:
        text = clean_ocr_text(raw_text)
        md_lines.append(f"## 第 {page_num} 页")
        md_lines.append("")
        md_lines.append(text)
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")

    return '\n'.join(md_lines)


def main():
    print("=" * 60)
    print("  虚拟数字人产品迭代文档 — PDF → Markdown 转换")
    print("=" * 60)

    # 1. Find tesseract
    tess_path = find_tesseract()
    pytesseract.pytesseract.tesseract_cmd = tess_path

    # 2. Ensure Chinese language data
    ensure_chinese_lang(tess_path)

    # 3. OCR all pages
    pages = ocr_pages(tess_path)

    # 4. Build MD
    md_content = build_markdown(pages)

    # 5. Write file
    OUTPUT_MD.write_text(md_content, encoding="utf-8")
    total_chars = len(md_content)
    total_text_chars = sum(len(t.strip()) for _, t in pages)

    print(f"\n{'='*60}")
    print(f"  DONE!")
    print(f"  Output: {OUTPUT_MD}")
    print(f"  Total characters: {total_chars:,}")
    print(f"  Extracted text:   {total_text_chars:,}")
    print(f"  Pages processed:  {len(pages)}")
    print(f"{'='*60}")

    # Print preview
    print(f"\n--- First 800 chars preview ---")
    print(md_content[:800])


if __name__ == "__main__":
    main()
