"""
命令行 Demo：快速测试地址审核 Agent

用法：
    cd address-audit-agent
    python examples/demo.py "北京市海淀区中关村大街1号"
    python examples/demo.py                          # 交互模式
"""

import sys
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import AddressAuditAgent


def main():
    print("=" * 60)
    print("   📍 地址信息审核 Agent — 命令行 Demo")
    print("=" * 60)
    print()

    # 创建 Agent
    try:
        agent = AddressAuditAgent()
    except ValueError as e:
        print(f"❌ 启动失败：{e}")
        print()
        print("请先配置 .env 文件：")
        print("  1. 复制 .env.example 为 .env")
        print("  2. 填入 LLM_API_KEY（DeepSeek 或 OpenAI）")
        print("  3. 填入 AMAP_API_KEY（高德地图）")
        return

    # 开场白
    greeting = agent.start()
    print(f"🤖 Agent: {greeting}")
    print()

    # 如果有命令行参数，直接审核
    if len(sys.argv) > 1:
        address = " ".join(sys.argv[1:])
        print(f"👤 输入: {address}")
        print()
        print("🤖 Agent 思考中...")
        print("-" * 60)
        result = agent.chat(address)
        print(result)
        print("-" * 60)
    else:
        # 交互模式
        print("输入地址开始审核，输入 'quit' 退出，输入 'reset' 重置会话")
        print()
        while True:
            try:
                user_input = input("👤 你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("再见！")
                break
            if user_input.lower() == "reset":
                agent.reset()
                greeting = agent.start()
                print(f"🤖 Agent: {greeting}")
                print()
                continue

            print()
            print("🤖 Agent 思考中...")
            print("-" * 60)
            result = agent.chat(user_input)
            print(result)
            print("-" * 60)
            print()


if __name__ == "__main__":
    main()
