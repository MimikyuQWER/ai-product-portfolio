"""
地址审核 Agent —— 真实 API 端到端测试用例（独立脚本）
========================================================
运行：python tests/test_live_api.py
前提：.env 中已配置 LLM_API_KEY（DeepSeek），高德 Key 由 .env.example 兜底。

覆盖：
- T0 前端辅助函数单测（依据分段 / 信息源列 / 六列与五列解析）
- T1 对话框直接审核（无预审）+ 五列表格 + 高德链接可溯源
- T2 文件上传：数据质量预审 → 确认 → 正式审核（全量不丢）
- T3 图片 OCR 文字质量预审（追问缺失）
- T4 实时进度回调（progress_callback 推送步骤日志）
- T5 web_search 多级回退（Bing CN / 百度 / DDG）真实可用且不超时

说明：每个用例独立新建 Agent 实例，避免消息上下文串扰。
"""

import sys
import io
import csv
import json
import os
import time
import importlib.util

# 把项目根目录加入 path，使 `import agent` 可用
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from agent.agent import AddressAuditAgent


# ---- 断言工具 ----
RESULTS = []


def check(name: str, cond: bool, detail: str = ""):
    RESULTS.append((name, cond, detail))
    mark = "PASS" if cond else "FAIL"
    print(f"[{mark}] {name}" + (f"  -> {detail}" if detail else ""))


def amap_link_present(text: str) -> bool:
    return ("uri.amap.com" in text) or ("ditu.amap.com" in text)


# ============================================================
# T0：前端辅助函数单测（不启动 streamlit 服务）
# ============================================================
def test_frontend_helpers():
    print("\n===== T0 前端辅助函数单测 =====")
    spec = importlib.util.spec_from_file_location("appmod", os.path.join(ROOT, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    basis = (
        "【标准一·完整详细】：地址包含省市区街道门牌号，完整度6级，符合要求。"
        "【标准二·可搜索核实】：高德地图精确定位到门址。<br>标准四（门牌号准确性）：门牌号可查。"
        "🔗 高德地图定位：https://uri.amap.com/marker?position=116.31,39.98&name=中关村大街1号 "
        "🔗 高德地图搜索：https://ditu.amap.com/search?query=中关村大街1号 "
        "🔗 来源网页：https://www.example.com/news/123"
    )
    fmt = mod._format_basis(basis)
    src = mod._build_source_cell(basis, "")
    check("T0a 依据按标准分段且小标题加粗",
          "**【标准一·完整详细】：**" in fmt and "**【标准二·可搜索核实】：**" in fmt
          and "**标准四（门牌号准确性）：**" in fmt and fmt.count("<br>") == 2)
    check("T0b 依据列不再残留链接", "http" not in fmt and "🔗" not in fmt)
    check("T0c 信息源列三类链接齐全且含区别说明",
          "高德地图定位链接" in src and "高德地图搜索链接" in src and "来源网页" in src and "说明" in src)

    tbl5 = ("| 序号 | 地址 | 审核结果 | 审核依据 | 审核信息源 |\n|---|---|---|---|---|\n"
            "| 1 | 北京市海淀区中关村大街1号 | 有效地址 | 依据文本 | 来源文本 |\n"
            "| 2 | 上海市 | 不确定 | 依据2 |  |\n")
    rows5 = mod._parse_audit_rows(tbl5)
    check("T0d 五列表格解析（含空信息源兼容）",
          len(rows5) == 2 and rows5[0]["审核信息源"] == "来源文本" and rows5[1]["审核信息源"] == "")

    tbl6 = ("| 序号 | 姓名 | 地址 | 审核结果 | 审核依据 | 审核信息源 |\n|---|---|---|---|---|---|\n"
            "| 1 | 张三 | 北京市海淀区中关村大街1号 | 有效地址 | 依据文本 | 来源文本 |\n"
            "| 2 | 李四 | 上海市 | 不确定 | 依据2 |  |\n")
    rows6 = mod._parse_audit_rows(tbl6)
    check("T0e 六列表格解析（含姓名列与空信息源）",
          len(rows6) == 2 and rows6[0]["姓名"] == "张三" and rows6[0]["审核信息源"] == "来源文本"
          and rows6[1]["姓名"] == "李四" and rows6[1]["审核信息源"] == "")


# ============================================================
# T1：对话框直接输入 → 直接审核（无预审）+ 五列表格 + 可溯源
# ============================================================
def test_direct_audit():
    print("\n===== T1 直接审核（无预审）+ 五列表格 =====")
    ag = AddressAuditAgent()
    out = ag.chat("请审核以下地址：故宫博物院")
    print("  --- 模型输出（节选） ---")
    print("  " + out.replace("\n", "\n  ")[:500])
    check("T1a 输出了五列审核表格", "|---" in out and "审核信息源" in out)
    check("T1b 判定为有效地址", "有效地址" in out)
    check("T1c 信息源含高德地图链接", amap_link_present(out))

    ag2 = AddressAuditAgent()
    out2 = ag2.chat("请审核以下地址：北京市")
    check("T1d 不完整地址未判为有效", "有效地址" not in out2 or "不确定" in out2 or "无效" in out2,
          detail=out2[:60].replace("\n", " "))


# ============================================================
# T2：文件上传 → 数据质量预审 → 确认 → 正式审核（全量不丢）
# ============================================================
def test_file_upload_flow():
    print("\n===== T2 文件上传：质量预审 → 确认 → 正式审核 =====")
    # 加载 app 模块以复用前端解析函数（与 T0 同款加载逻辑）
    spec = importlib.util.spec_from_file_location("appmod", os.path.join(ROOT, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["姓名", "地址"])
    w.writerow(["张三", "故宫博物院"])      # 唯一精确匹配（兴趣点）→ 预期 有效地址 + 高德定位链接
    w.writerow(["李四", "北京市"])          # 不完整地址 → 不确定
    csv_bytes = buf.getvalue().encode("utf-8-sig")

    ag = AddressAuditAgent()
    ok_pre, pre = ag.prepare_excel_audit(csv_bytes, "test.csv")
    check("T2a 生成了数据质量预审报告", ("补充" in pre or "缺失" in pre or "完整" in pre))
    check("T2b 预审阶段未直接出审核表", "共审核" not in pre)
    check("T2b2 预审返回 (ok, text) 元组且 ok=True", ok_pre is True)

    final = ag.confirm_and_audit(supplement="以上地址均真实存在，请正式核验")
    print("  --- 正式审核输出（节选） ---")
    print("  " + final.replace("\n", "\n  ")[:500])
    check("T2c 正式审核产出六列表格（含姓名列）",
          "| 序号 | 姓名 | 地址 |" in final and "审核信息源" in final and "|---" in final)
    check("T2d 全量处理未丢数据（2/2）", "共审核 2 / 2" in final)
    check("T2e 有效地址含高德定位链接", amap_link_present(final))

    rows_f = mod._parse_audit_rows(final)
    valid_rows = [r for r in rows_f if "有效地址" in r.get("审核结果", "")]
    link_in_valid = any(
        amap_link_present(r.get("审核信息源", "") + " " + r.get("审核依据", ""))
        for r in valid_rows
    )
    check("T2f 有效地址行确实带回高德定位链接",
          link_in_valid, detail=f"有效行数={len(valid_rows)}")


# ============================================================
# T3：图片 OCR 文字 → 数据质量预审（追问缺失）
# ============================================================
def test_ocr_quality():
    print("\n===== T3 图片 OCR 文字质量预审 =====")
    ocr_text = "客户姓名：王五\n身份证地址：广州市天河区天河路\n（门牌号被遮挡）"
    ag = AddressAuditAgent()
    rep = ag.assess_ocr_quality(ocr_text, "id_card.png")
    check("T3a 生成 OCR 质量预审报告", ("补充" in rep or "缺失" in rep or "完整" in rep))
    check("T3b OCR 预审未直接出审核表", "共审核" not in rep)


# ============================================================
# T4：实时进度回调（progress_callback 推送步骤日志）
# ============================================================
def test_progress_callback():
    print("\n===== T4 实时进度回调 =====")
    pushes: list[list[dict]] = []
    ag = AddressAuditAgent()
    ag.progress_callback = lambda log: pushes.append(log)
    ag.chat("请审核以下地址：北京市海淀区中关村大街1号")
    ag.progress_callback = None
    flat_texts = [e.get("text", "") for p in pushes for e in p]
    check("T4a 审核过程中有多次进度推送", len(pushes) >= 2, detail=f"共 {len(pushes)} 次推送")
    check("T4b 进度包含工具调用记录", any("高德" in t or "核验" in t for t in flat_texts),
          detail=" / ".join(flat_texts[:6]))


# ============================================================
# T5：web_search 多级回退真实可用且不超时
# ============================================================
def test_web_search_fallback():
    print("\n===== T5 web_search 多级回退 =====")
    from agent.tools import web_search
    t = time.time()
    data = json.loads(web_search("北京市海淀区中关村大街1号"))
    cost = time.time() - t
    print(f"  source={data.get('source')} total={data.get('total')} 耗时={cost:.2f}s")
    check("T5a 搜索成功且有结果", data.get("status") == "success" and data.get("total", 0) > 0)
    check("T5b 单次搜索不超时（<8s）", cost < 8.0, detail=f"{cost:.2f}s")
    check("T5c 结果含可溯源 URL", any(r.get("url", "").startswith("http") for r in data.get("results", [])))


# ============================================================
# T6：大文件多批次（分块逐批审核 + 上下文裁剪）—— 覆盖 Issue #3 的慢/卡根因
# ============================================================
def test_file_multi_batch():
    print("\n===== T6 大文件多批次（分块逐批审核 + 上下文裁剪）=====")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["姓名", "地址"])
    for i in range(12):
        w.writerow([f"用户{i}", "北京市海淀区中关村大街1号"])  # 12 条 → 3 批（每批 5 条）
    csv_bytes = buf.getvalue().encode("utf-8-sig")

    ag = AddressAuditAgent()
    ag.prepare_excel_audit(csv_bytes, "big.csv")
    final = ag.confirm_and_audit()
    check("T6a 全量 12 条处理不丢（3 批）", "共审核 12 / 12" in final)
    check("T6b 最终报告含高德定位链接", amap_link_present(final))
    # 上下文裁剪：finalize 后 LLM 上下文应被重置为 [system]，不再随批次无限膨胀
    check("T6c 审核后 LLM 上下文已重置（不再累积）", len(ag.messages) <= 2,
          detail=f"messages={len(ag.messages)}")


# ============================================================
# T7：geocode 健壮性（无网络，monkeypatch httpx）—— 覆盖 🔴-2 / 🔴-3
# ============================================================
class _FakeResp:
    """模拟 httpx.get 返回的响应对象"""
    def __init__(self, payload: dict, status: int = 200):
        self._p = payload
        self.status_code = status
    def json(self):
        return self._p


def test_geocode_robustness():
    print("\n===== T7 geocode 健壮性（API 故障 / 多候选）=====")
    import agent.tools as T

    orig_get = T.httpx.get
    orig_cfg = T._get_config
    # 强制提供一个 AMAP Key，避免触发"未配置"分支
    T._get_config = lambda k, d="": "test-key" if k == "AMAP_API_KEY" else orig_cfg(k, d)
    try:
        # 场景 1：高德返回 status != "1"（Key 失效 / 配额耗尽）—— 必须上报 error，不得伪装 found=false
        T.httpx.get = lambda *a, **kw: _FakeResp(
            {"status": "0", "info": "INVALID_USER_KEY", "infocode": "10001"}
        )
        out1 = json.loads(T.geocode("任意地址"))
        check("T7a 高德故障返回 status=error（非 found=false）",
              out1.get("status") == "error", detail=out1.get("message", "")[:40])
        check("T7b error 提示应判不确定（不得误导为无效）",
              "不确定" in out1.get("message", ""))

        # 场景 2：高德匹配到多个地点（count>1）—— 需暴露 match_count / is_unique=False
        T.httpx.get = lambda *a, **kw: _FakeResp({
            "status": "1", "count": "3",
            "geocodes": [
                {"formatted_address": "A1", "location": "116.1,39.1", "level": "兴趣点"},
                {"formatted_address": "A2", "location": "116.2,39.2", "level": "兴趣点"},
                {"formatted_address": "A3", "location": "116.3,39.3", "level": "兴趣点"},
            ],
        })
        out2 = json.loads(T.geocode("模糊地址"))
        check("T7c 多候选暴露 match_count", out2.get("match_count") == 3)
        check("T7d 多候选 is_unique=False", out2.get("is_unique") is False)
        check("T7e 多候选仍回带高德链接（map_url/marker_url）",
              bool(out2.get("map_url")) or bool(out2.get("marker_url")))
    finally:
        T.httpx.get = orig_get
        T._get_config = orig_cfg


# ============================================================
# T8：_match_chunk 防串号 —— 覆盖 🟠-8
# ============================================================
def test_match_chunk_no_mismatch():
    print("\n===== T8 _match_chunk 防串号 =====")
    from agent.agent import AddressAuditAgent

    chunk = [{"idx": 1, "name": "张三", "address": "北京市海淀区中关村大街1号"}]

    # 场景 1：模型正确回显 → 映射到 idx=1
    rows_ok = [{"序号": "1", "姓名": "张三", "地址": "北京市海淀区中关村大街1号",
                "审核结果": "有效地址", "审核依据": "x", "审核信息源": "y"}]
    r1, e1 = {}, []
    AddressAuditAgent._match_chunk(chunk, rows_ok, r1, e1)
    check("T8a 正确回显映射到文件序号 idx=1", 1 in r1 and len(e1) == 0)

    # 场景 2：模型把 B 的地址挂到了序号 1（串号）→ 不得误挂，进 extra
    rows_bad = [{"序号": "1", "姓名": "张三", "地址": "上海市南京东路",
                 "审核结果": "有效地址", "审核依据": "x", "审核信息源": "y"}]
    r2, e2 = {}, []
    AddressAuditAgent._match_chunk(chunk, rows_bad, r2, e2)
    check("T8b 地址串号不误挂到 idx=1", 1 not in r2)
    check("T8c 串号行进入 extra_rows 防丢数据", len(e2) == 1)


# ============================================================
# 主流程
# ============================================================
def main():
    print("开始端到端测试用例（真实 DeepSeek + 真实高德 + 真实联网搜索回退链）\n")
    for fn in (test_frontend_helpers, test_direct_audit, test_file_upload_flow,
               test_ocr_quality, test_progress_callback, test_web_search_fallback,
               test_file_multi_batch, test_geocode_robustness, test_match_chunk_no_mismatch):
        try:
            fn()
        except Exception as e:
            check(f"{fn.__name__} 执行异常", False, detail=f"{type(e).__name__}: {e}")

    passed = sum(1 for _, c, _ in RESULTS if c)
    total = len(RESULTS)
    print(f"\n===== 测试结果：{passed}/{total} 通过 =====")
    if passed != total:
        print("存在失败用例，请检查上方 FAIL 详情。")
        sys.exit(1)
    print("全部用例通过 ✓")


if __name__ == "__main__":
    main()
