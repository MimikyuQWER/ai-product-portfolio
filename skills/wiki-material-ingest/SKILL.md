---
name: wiki-material-ingest
description: 将金融研报 PDF/PPTX 材料导入个人知识库 raw/ 目录。当用户提到"导入素材""材料入库""raw转换""PDF转Markdown""增强提取""批量转换研报""双工具对比"时使用。务必在涉及金融研报文件需要导入wiki raw/时触发此skill——即使pdf skill也能处理PDF，本skill提供金融研报专用的对比择优+增强提取+质量检查流程。
---

# Wiki 材料入库

> 将金融研报 PDF/PPTX 转换为 Markdown 存入 raw/，含双工具对比择优 + 增强提取（表格/图片）+ 质量控制。

## 工作流

```
1. 调用 pdf skill → 基础文本提取
2. 双工具对比（MarkItDown vs pdfplumber）
3. 自动择优 → 保留质量更好的版本
4. 增强提取：文本 + 表格 + 图片标记
5. 质量控制检查 → 存入 raw/
```

## 步骤

### Step 1：确认源和目标

- 源目录：用户指定的 PDF/PPTX 文件或目录
- 目标：`~/knowledge-wiki/raw/上农商资管材料/`（或其他 raw/ 子目录）
- 检查目标是否有已有版本 → 有则标注为覆盖或跳过

### Step 2：调用 pdf skill 做基础提取

pdf skill 已安装于 `~/.claude/skills/pdf/`，提供 pdfplumber/pypdf 基础能力。本 skill 在此基础上增加对比择优和增强提取。

### Step 3：双工具对比择优

使用 `scripts/convert_compare.py`：
- PDF：MarkItDown 得分 vs pdfplumber 得分 → 选高分
- PPTX：仅 MarkItDown（原生格式，质量好）
- 打分维度：颜色值残留、空表格碎片、数字碎片、文本密度
- 详见 `references/tool-comparison.md`

### Step 4：增强提取

使用 `scripts/batch_enhance.py`：
- 文本内容（保持布局）
- 表格：`### 📊 表格X.Y` 标记 + Markdown 格式
- 图片：`![图表X_Y]` 标记（图片文件需另外从PDF导出）

### Step 5：质量控制

检查清单（详见 `references/quality-checklist.md`）：
- [ ] 颜色值残留 < 100 处
- [ ] 空表格碎片 < 200 处
- [ ] 文本密度 > 2000 字符
- [ ] 表格数量 > 0（如果原PDF有表格）
- [ ] 输出文件大小合理（不低于原文件的30%）

### Step 6：入库并 commit

```
git add raw/ && git commit -m "raw: {文件名}入库——{N}表格{M}图片"
```

## 关键原则

- **先单文件测试，再全量跑** — 避免批量跑完发现质量问题
- **给用户看进度条** — 超过 2 分钟的任务必须有可视化进度
- **保存旧版本** — 增强提取前确认用户是否需要保留旧 raw
