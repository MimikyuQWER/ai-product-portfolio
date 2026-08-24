# Knowledge Wiki 项目指令

> 当你在 `C:\Users\张逸帆\knowledge-wiki` 目录下工作时，你是这个 wiki 的维护者。

## 必读

首先阅读 `SCHEMA.md`——它定义了页面类型、操作流程、所有规范。

## 快速操作

| 用户说 | 做什么 |
|---|---|
| "沉淀 wiki" | 提取对话产出 → 写入对应页面 → 更新 index → git commit |
| "摄入这个：{内容}" | 读 → 总结确认 → 更新页面 → 更新 index → git commit |
| "记一下：{内容}" | inbox/ 写入或直接更新相关页面 |
| "整理一下" / "整理 inbox" | 执行健康检查（SCHEMA.md 操作流程-Lint） |

## 原则

- 默认更新旧页面，不建新页面
- 每次实质更新后 git commit（格式：`{操作}: {简述}`）
- 不确定就问用户
