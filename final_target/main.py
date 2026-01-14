import os
import time

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ⚠️ 注意：以下需要确保 'langchain_qwq' 模块和 'ChatQwen' 类可以正确导入
load_dotenv()

# 模型密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")  # qwen
AMAP_API_KEY = os.getenv("AMAP_API_KEY")
JUHE_TRAIN_API_KEY = os.getenv("JUHE_TRAIN_API_KEY")
SERPAPI_FLIGHTS_API_KEY = os.getenv("SERPAPI_FLIGHTS_API_KEY")
# 并且您的 QWEN_API_KEY 已经配置在环境变量中。
try:
    from langchain_qwq import ChatQwen
except ImportError:
    print("❌ 错误：请确保 'langchain_qwq' 已正确安装并可导入。")
    exit()

# 1. 模型初始化 (使用您提供的参数)
# 假设 ChatQwen 能够从环境变量中自动获取 API Key
qwen_max = ChatQwen(
    model="qwen-max",
    temperature=0.5,
    timeout=30.0  # 我们设置的超时时间
)

# 2. 定义一个简单的 Prompt
# 目标：测试模型在执行复杂指令（需要推理）时的响应时间
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的决策助手，专注于推理和逻辑。"),
    ("user", "请总结以下内容，并以中文回复：Why is the sky blue? Explain it in 3 detailed, numbered steps.")
])

# 3. 创建执行链 (Chain)
chain = prompt | qwen_max | StrOutputParser()

# 4. 执行测试
print("--- 🚀 开始测试 Qwen-Max 模型响应 ---")
start_time = time.time()

try:
    # 异步执行，如果您在 LangGraph 中是异步调用的话
    # 对于简单的同步测试，可以直接调用 invoke
    response = chain.invoke({})

    end_time = time.time()
    elapsed_time = end_time - start_time

    print("\n--- ✅ 测试成功 ---")
    print(f"模型响应时间: {elapsed_time:.2f} 秒")
    print("模型输出:")
    print("--------------------------------")
    print(response.strip())
    print("--------------------------------")

except Exception as e:
    end_time = time.time()
    elapsed_time = end_time - start_time

    print("\n--- ❌ 测试失败 ---")
    print(f"执行耗时: {elapsed_time:.2f} 秒")
    print(f"错误信息: {e}")
    # 特别检查是否因为超时失败
    if "timeout" in str(e).lower():
        print("💡 结论：模型在 30 秒内没有响应，超时设置生效（但模型仍需优化响应速度）。")