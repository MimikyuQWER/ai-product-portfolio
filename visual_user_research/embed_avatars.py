"""
Embed avatar base64 data into V3 HTML — v2: use <img> tags instead of background-image.
"""
from pathlib import Path

WORK_DIR = Path(r"D:\就业学习资料包251116\秋招AI产品项目\visual_user_research")
HTML_IN = WORK_DIR / "虚拟人demoV3 260724.html"
HTML_OUT = WORK_DIR / "虚拟人demoV3 260726.html"
BASE64_JS = WORK_DIR / "_avatar_base64.js"

base64_content = BASE64_JS.read_text(encoding="utf-8")
html = HTML_IN.read_text(encoding="utf-8")

# ── 1. Insert base64 data ──
script_insert = base64_content + "\n\n// ─────────── USER DATABASE (28 users) ───────────"
html = html.replace(
    "// ─────────── USER DATABASE (9 users) ───────────",
    script_insert
)

# ── 2. Add avatar helper function right after AVATAR_BASE64 ──
# Insert after the closing "};" of AVATAR_BASE64, before USER DATABASE comment
helper_func = """
function avatarHTML(uid) {
  var b64 = AVATAR_BASE64[uid];
  if (b64) {
    return '<img src=\"' + b64 + '\" class=\"avatar-img\" alt=\"\">';
  }
  return uid;
}
"""
html = html.replace(
    "// ─────────── USER DATABASE (28 users) ───────────",
    helper_func + "\n// ─────────── USER DATABASE (28 users) ───────────"
)

# ── 3. Add CSS for avatar-img ──
old_avatar = """    .avatar {
      width: 46px;
      height: 46px;
      border-radius: 50%;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: #dfe7ff;
      color: #3156d3;
      font-weight: 700;
      font-size: 15px;
      flex: 0 0 auto;
    }"""
new_avatar = """    .avatar {
      width: 46px; height: 46px; border-radius: 50%;
      display: inline-flex; align-items: center; justify-content: center;
      background: #dfe7ff; color: #3156d3; font-weight: 700; font-size: 15px;
      flex: 0 0 auto; overflow: hidden; position: relative;
    }
    .avatar-img {
      width: 100%; height: 100%; border-radius: 50%;
      object-fit: cover; display: block; position: absolute;
      top: 0; left: 0;
    }"""
html = html.replace(old_avatar, new_avatar)

# ── 4. Card avatar: use avatarHTML() helper ──
old_card = '<div class="avatar">${u.avatar}</div>'
new_card = '<div class="avatar">${avatarHTML(u.avatar)}</div>'
html = html.replace(old_card, new_card)

# ── 5. Profile avatar ──
old_prof = '<div class="avatar xl">${u.avatar}</div>'
new_prof = '<div class="avatar xl">${avatarHTML(u.avatar)}</div>'
html = html.replace(old_prof, new_prof)

# ── 6. Chat header avatar ──
old_chat = '      document.getElementById("chatAvatar").textContent = u.avatar;'
new_chat = '      document.getElementById("chatAvatar").innerHTML = avatarHTML(u.avatar);'
html = html.replace(old_chat, new_chat)

# ── 7. Update counts ──
html = html.replace(
    '当前共 <span id="totalUserCount">9</span> 位用户',
    '当前共 <span id="totalUserCount">28</span> 位用户'
)
html = html.replace(
    '<span id="shownCount">9</span>人',
    '<span id="shownCount">28</span>人'
)

# ── 8. Use real names instead of shortName ──
html = html.replace(
    '                <p class="card-name">${u.shortName}</p>',
    '                <p class="card-name">${u.name}</p>'
)
html = html.replace(
    '      document.getElementById("chatName").textContent = u.shortName;',
    '      document.getElementById("chatName").textContent = u.name;'
)
html = html.replace(
    '      document.getElementById("sideSummary").textContent = `${u.shortName}：${u.cardDesc}`;',
    '      document.getElementById("sideSummary").textContent = `${u.name}：${u.cardDesc}`;'
)

HTML_OUT.write_text(html, encoding="utf-8")

# Verify
assert "avatarHTML" in html
assert "avatar-img" in html
assert "AVATAR_BASE64" in html

print(f"Output: {HTML_OUT}")
print(f"Size: {HTML_OUT.stat().st_size / 1024:.0f} KB")
print("28 avatars embedded via <img> tags + avatarHTML() helper")
