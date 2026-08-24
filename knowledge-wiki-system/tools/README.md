# Tools — 可复用脚本资产

> 每个脚本完成一个独立任务。已验证可用，新任务优先复用而非重写。

## 数据管道

| 脚本 | 用途 | 用法 |
|------|------|------|
| `batch_enhance.py` | 全量PDF增强提取（文本+表格+图片标记） | `python batch_enhance.py` |
| `convert_compare.py` | 双工具（MarkItDown vs pdfplumber）转换对比择优 | `python convert_compare.py` |
| `ingest_materials.py` | MarkItDown批量转换PDF/PPTX→Markdown入库 | `python ingest_materials.py` |

## Wiki 维护

| 脚本 | 用途 | 用法 |
|------|------|------|
| `merge_single_file.py` | AI版+Full版合并为单文件（带大纲索引+去重） | `python merge_single_file.py` |

## 外部同步

| 脚本 | 用途 | 用法 |
|------|------|------|
| `sync_feishu.py` | 飞书知识库增量同步（支持headless自动刷新token） | `python sync_feishu.py --headless` |

## 其他

| 文件 | 用途 |
|------|------|
| `cc-status-light.py` | CC运行状态桌面悬浮指示灯（待修复） |
| `setup_scheduled_task.ps1` | Windows定时任务配置（待验证） |
