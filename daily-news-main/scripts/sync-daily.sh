#!/bin/bash
# 每天定时从 GitHub 拉取最新的日报内容
# 只更新 daily/ 和 daily-assets/ 目录，不影响本地代码修改

cd /data/projects/ruolanxin.li/daily2

# 先 fetch 远程最新
git fetch origin main 2>/dev/null

# 只 checkout 远程的 daily 内容目录（不影响其他文件）
git checkout origin/main -- daily/ 2>/dev/null
git checkout origin/main -- daily-assets/ 2>/dev/null

# 同时拉取数据库（如果有 commit 记录更新）
git checkout origin/main -- data/ 2>/dev/null

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Daily content synced from GitHub"
