import ngrok
import asyncio
import os


async def start_tunnel():
    # 1. 填入你的 Token
    token = "38C9Twad1jlgR9XsVDGYrnoMvAR_7xvr735JZJqLbJu6EfBmt"

    print("--- 正在连接 ngrok 服务器... ---")
    try:
        # 注意：这里将 8000 改为了字符串 "8000"
        session = await ngrok.connect(authtoken=token)
        listener = await session.forward("localhost:8000")

        print("\n" + "=" * 60)
        print(f"✅ 隧道建立成功!")
        print(f"🔗 公网访问地址: {listener.url()}")
        print("=" * 60)
        print("\n💡 下一步：")
        print(f"1. 确保你的 api_bridge.py 正在运行且监听 8000 端口。")
        print(f"2. 在浏览器打开 {listener.url()}/docs 确认是否通畅。")

        await asyncio.Event().wait()
    except Exception as e:
        print(f"❌ 隧道连接失败: {e}")


if __name__ == "__main__":
    asyncio.run(start_tunnel())