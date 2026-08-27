# -*- coding: utf-8 -*-
"""core/ — 系统唯一计算内核。

全系统只有一个真相来源：
  - core/metrics.py     — 所有金融指标计算的唯一实现
  - core/data_loader.py — 统一数据读取接口（策略只调这个）
  - core/validators.py  — 未来函数检测、架构违规检查

其他所有目录（factors/、strategy/、engine/、scripts/）只能 import，禁止重新实现。
"""
