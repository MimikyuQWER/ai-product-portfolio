"""
Batch resize avatar photos → base64 → embed in HTML.
Reads avatar_XX_name.png and extracts user_id from filename.
"""
import base64
from io import BytesIO
from pathlib import Path
from PIL import Image

WORK_DIR = Path(r"D:\就业学习资料包251116\秋招AI产品项目\visual_user_research")
PHOTO_DIR = WORK_DIR / "photos"
OUTPUT_JS = WORK_DIR / "_avatar_base64.js"

TARGET_SIZE = (256, 256)
JPEG_QUALITY = 80

photos = sorted(PHOTO_DIR.glob("avatar_*.png"))
print(f"Found {len(photos)} avatar files")

avatar_base64 = {}
stats = []

for photo_path in photos:
    fname = photo_path.stem  # e.g. "avatar_07_marcus_chen"
    parts = fname.split("_")
    user_id = parts[1]  # "07"

    img = Image.open(photo_path)
    original_size = img.size

    # Convert RGBA → RGB
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        img = Image.alpha_composite(bg, img)
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    img = img.resize(TARGET_SIZE, Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    jpeg_bytes = buf.getvalue()

    b64 = base64.b64encode(jpeg_bytes).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{b64}"

    avatar_base64[user_id] = data_uri

    kb = len(jpeg_bytes) / 1024
    stats.append((user_id, fname, original_size, kb))
    print(f"  [{user_id}] {fname} {original_size[0]}x{original_size[1]} → {TARGET_SIZE[0]}x{TARGET_SIZE[1]}, {kb:.1f} KB")

# Write JS
total_kb = sum(s[3] for s in stats)
js_lines = [
    "// Auto-generated avatar base64 data",
    f"// {len(stats)} avatars, total {total_kb:.0f} KB",
    "const AVATAR_BASE64 = {",
]
for uid in sorted(avatar_base64.keys(), key=lambda x: int(x)):
    js_lines.append(f'  "{uid}": "{avatar_base64[uid]}",')
js_lines.append("};")

OUTPUT_JS.write_text("\n".join(js_lines), encoding="utf-8")

print(f"\nDone: {len(stats)} avatars → {OUTPUT_JS.name}")
print(f"Total size: {total_kb:.0f} KB ({total_kb/1024:.1f} MB)")
missing = set(f"{i:02d}" for i in [2,4,5,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,33,42,55]) - set(avatar_base64.keys())
if missing:
    print(f"Missing users: {missing}")
else:
    print("All 28 users covered")
