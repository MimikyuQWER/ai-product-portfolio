"""
飞书知识库同步脚本（增强版）
============================
- 增量同步：比对文档内容 hash，只更新变化的文档
- 变更追踪：写入 raw/feishu/.changes.json，供 auto_digest 识别
- 无头模式：定时任务运行时跳过交互式 OAuth，用 refresh_token 续期
- 交互式模式：手动运行时可走完整 OAuth 流程

用法：
  python sync_feishu.py              # 交互式（手动跑）
  python sync_feishu.py --headless   # 无头模式（定时任务用）

依赖：pip install requests
"""

import requests
import json
import hashlib
import os
import sys
import time
import webbrowser
import urllib.parse
from pathlib import Path

# 修复 Windows 中文终端 emoji 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# 配置
# ============================================================
APP_ID = os.environ.get("FEISHU_APP_ID", "cli_aacf4e96bef99bd5")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
if not APP_SECRET:
    raise RuntimeError("请设置环境变量 FEISHU_APP_SECRET，或在 .env 文件中配置。为保护密钥安全，不再支持硬编码。")
REDIRECT_URI = "http://127.0.0.1:9999/callback"

# 路径
WIKI_DIR = Path(__file__).resolve().parent.parent  # knowledge-wiki/
RAW_DIR = WIKI_DIR / "raw" / "feishu"
TOKEN_FILE = WIKI_DIR / ".feishu_tokens.json"
CHANGES_FILE = RAW_DIR / ".changes.json"
LAST_SYNC_FILE = RAW_DIR / ".last_sync"

# API 基础 URL
API_BASE = "https://open.feishu.cn/open-apis"


# ============================================================
# Token 管理
# ============================================================

def get_tenant_token():
    resp = requests.post(
        f"{API_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 tenant token 失败: {data}")
    return data["tenant_access_token"]


def load_saved_tokens():
    if TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_tokens(tokens):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(
        json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def refresh_user_token(refresh_token):
    tenant_token = get_tenant_token()
    resp = requests.post(
        f"{API_BASE}/authen/v1/oidc/refresh_access_token",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"刷新 token 失败: {data}")
    d = data.get("data", data)
    return {
        "user_access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", refresh_token),
        "expires_at": time.time() + d.get("expires_in", 7200),
    }


def get_user_token(headless=False):
    saved = load_saved_tokens()

    # 1. 本地有且未过期
    if saved.get("user_access_token") and saved.get("expires_at", 0) > time.time() + 300:
        return saved["user_access_token"]

    # 2. 有 refresh_token，尝试刷新
    if saved.get("refresh_token"):
        try:
            new_tokens = refresh_user_token(saved["refresh_token"])
            save_tokens({**saved, **new_tokens})
            return new_tokens["user_access_token"]
        except Exception as e:
            if headless:
                raise RuntimeError(f"无头模式下 token 刷新失败，请手动运行一次授权: {e}")
            print(f"⚠️  刷新失败: {e}，需要重新授权")

    # 3. 无头模式不能交互，直接报错
    if headless:
        raise RuntimeError("无有效 token 且无头模式无法交互授权，请手动运行 python sync_feishu.py 完成授权")

    # 4. 交互式 OAuth
    return oauth_flow()


def oauth_flow():
    state = "feishu_sync_" + str(int(time.time()))
    scopes = "wiki:wiki:readonly wiki:space:retrieve docx:document:readonly drive:drive:readonly"
    auth_url = (
        f"{API_BASE}/authen/v1/authorize"
        f"?app_id={APP_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI, safe='')}"
        f"&state={state}"
        f"&scope={urllib.parse.quote(scopes, safe='')}"
    )

    print("\n" + "=" * 60)
    print("飞书授权指引")
    print("=" * 60)
    print("\n1. 浏览器会自动打开飞书授权页面")
    print("2. 点击「授权」确认")
    print("3. 授权后浏览器地址栏会变成：")
    print("   http://127.0.0.1:9999/callback?code=xxxxxxxx&state=...")
    print("4. 把地址栏里的完整 URL 复制下来，粘贴到下面\n")

    webbrowser.open(auth_url)

    callback_url = input("👉 粘贴回调 URL: ").strip()
    parsed = urllib.parse.urlparse(callback_url)
    params = urllib.parse.parse_qs(parsed.query)
    auth_code = params.get("code", [None])[0]

    if not auth_code:
        print("❌ 未从 URL 中找到授权码")
        sys.exit(1)

    tenant_token = get_tenant_token()
    resp = requests.post(
        f"{API_BASE}/authen/v1/oidc/access_token",
        headers={"Authorization": f"Bearer {tenant_token}"},
        json={"grant_type": "authorization_code", "code": auth_code},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 user token 失败: {data}")

    d = data.get("data", data)
    tokens = {
        "user_access_token": d["access_token"],
        "refresh_token": d.get("refresh_token", ""),
        "expires_at": time.time() + d.get("expires_in", 7200),
    }
    save_tokens(tokens)
    print("✅ 授权完成，token 已保存")
    return tokens["user_access_token"]


# ============================================================
# Wiki API 操作
# ============================================================

def api_get(user_token, path, params=None):
    resp = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {user_token}"},
        params=params,
        timeout=30,
    )
    data = resp.json()
    if data.get("code") != 0:
        code = data.get("code")
        if code not in (99991674,):  # 静默跳过无权限
            print(f"  ⚠️ API [{code}]: {data.get('msg', '')[:120]}")
        return None
    return data.get("data", {})


def list_spaces(user_token):
    result = api_get(user_token, "/wiki/v2/spaces")
    if not result:
        return []
    return result.get("items", [])


def list_nodes(user_token, space_id, parent_node_token=None):
    all_nodes = []
    page_token = None
    while True:
        params = {"page_size": 50}
        if page_token:
            params["page_token"] = page_token
        if parent_node_token:
            params["parent_node_token"] = parent_node_token
        result = api_get(user_token, f"/wiki/v2/spaces/{space_id}/nodes", params)
        if not result:
            break
        all_nodes.extend(result.get("items", []))
        if not result.get("has_more"):
            break
        page_token = result.get("page_token")
    return all_nodes


def get_doc_raw_content(user_token, doc_id):
    result = api_get(user_token, f"/docx/v1/documents/{doc_id}/raw_content")
    if not result:
        return None
    return result.get("content", "")


def get_doc_meta(user_token, doc_id):
    """获取文档元信息，含 update_time"""
    return api_get(user_token, f"/docx/v1/documents/{doc_id}")


# ============================================================
# 同步逻辑（增量模式）
# ============================================================

def sanitize(filename):
    invalid = '<>:"/\\|?*\n\r'
    for ch in invalid:
        filename = filename.replace(ch, "_")
    return filename.strip()[:100]


def content_hash(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def load_changelog():
    if CHANGES_FILE.exists():
        try:
            return json.loads(CHANGES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_changelog(log):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CHANGES_FILE.write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_change(space_name, title, action, filepath=None):
    """记录变更"""
    log = load_changelog()
    entry = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "space": space_name,
        "title": title,
        "action": action,  # "new" | "updated" | "deleted"
        "file": str(filepath) if filepath else None,
    }
    log.insert(0, entry)
    # 只保留最近 200 条
    save_changelog(log[:200])
    return entry


def process_nodes(user_token, space_name, node_list, dir_path, depth=0):
    """
    递归同步节点（增量比对）。
    返回统计: {"new": N, "updated": N, "skipped": N, "errors": N}
    """
    stats = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}

    for node in node_list:
        ntype = node.get("obj_type", "doc")
        ntitle = node.get("title", "未命名")
        ntoken = node.get("node_token", "")
        doc_id = node.get("obj_token", "")
        sid = node.get("space_id", "")
        prefix = "  " * depth

        if ntype == "folder":
            subdir = dir_path / sanitize(ntitle)
            subdir.mkdir(parents=True, exist_ok=True)
            children = list_nodes(user_token, sid, ntoken)
            sub_stats = process_nodes(user_token, space_name, children, subdir, depth + 1)
            for k in stats:
                stats[k] += sub_stats[k]
            continue

        if ntype not in ("doc", "docx"):
            continue

        if not doc_id:
            stats["errors"] += 1
            continue

        fname = sanitize(ntitle) + ".md"
        fpath = dir_path / fname

        # === 下载远程内容 ===
        remote_content = get_doc_raw_content(user_token, doc_id)
        if remote_content is None:
            stats["errors"] += 1
            continue

        # === 构建完整文件内容（含 frontmatter） ===
        frontmatter = (
            f"---\n"
            f"source: feishu\n"
            f"space: {space_name}\n"
            f"title: {ntitle}\n"
            f"doc_id: {doc_id}\n"
            f"synced_at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"domain: 通用\n"
            f"---\n\n"
        )
        full_content = frontmatter + remote_content
        new_hash = content_hash(full_content)

        # === 比对本地文件 ===
        if fpath.exists():
            local_hash = content_hash(fpath.read_text(encoding="utf-8"))
            if local_hash == new_hash:
                stats["skipped"] += 1
                continue
            # 内容变了 → 更新
            fpath.write_text(full_content, encoding="utf-8")
            add_change(space_name, ntitle, "updated", fpath)
            stats["updated"] += 1
            print(f"{prefix}🔄 {ntitle}（已更新）")
        else:
            # 新文件
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(full_content, encoding="utf-8")
            add_change(space_name, ntitle, "new", fpath)
            stats["new"] += 1
            print(f"{prefix}🆕 {ntitle}")

    return stats


def sync_all(headless=False):
    """主流程"""
    if not headless:
        print("=" * 60)
        print("🚀 飞书知识库同步")
        print("=" * 60)

    # 1. 获取 token
    user_token = get_user_token(headless=headless)

    # 2. 列出知识库
    spaces = list_spaces(user_token)
    if not spaces:
        print("⚠️  未找到任何知识库")
        return

    total_stats = {"new": 0, "updated": 0, "skipped": 0, "errors": 0}

    # 3. 遍历同步（先清空本次变更记录）
    save_changelog([])

    for space in spaces:
        space_id = space["space_id"]
        space_name = space["name"]
        print(f"\n📚 {space_name}")
        print("-" * 40)

        space_dir = RAW_DIR / sanitize(space_name)
        space_dir.mkdir(parents=True, exist_ok=True)

        nodes = list_nodes(user_token, space_id)
        if not nodes:
            print("  📭 空")
            continue

        stats = process_nodes(user_token, space_name, nodes, space_dir, depth=1)
        for k in total_stats:
            total_stats[k] += stats[k]

    # 4. 记录同步时间
    LAST_SYNC_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_SYNC_FILE.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")

    # 5. 输出小结
    print(f"\n{'=' * 60}")
    print(f"📊 同步结果")
    print(f"{'=' * 60}")
    print(f"  🆕 新增: {total_stats['new']}")
    print(f"  🔄 更新: {total_stats['updated']}")
    print(f"  ⏭️  跳过: {total_stats['skipped']}")
    print(f"  ❌ 失败: {total_stats['errors']}")

    changes = load_changelog()
    if changes and not headless:
        print(f"\n📋 变更详情:")
        for c in changes:
            emoji = {"new": "🆕", "updated": "🔄", "deleted": "🗑️"}.get(c["action"], "❓")
            print(f"  {emoji} [{c['space']}] {c['title']}")

    has_new_or_updated = total_stats["new"] + total_stats["updated"] > 0
    if has_new_or_updated:
        print(f"\n💡 有 {total_stats['new'] + total_stats['updated']} 个变更，下次 CC 对话结束时会自动处理")

    print(f"📂 文件路径: {RAW_DIR}")
    return has_new_or_updated


if __name__ == "__main__":
    headless = "--headless" in sys.argv
    sync_all(headless=headless)
