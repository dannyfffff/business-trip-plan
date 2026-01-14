import uuid
from fastapi import FastAPI, Body
from typing import Dict, Any

# 导入你现有的逻辑
from graph import build_travel_graph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

app = FastAPI(title="商务行程规划 API 桥接器")

# 1. 初始化图和持久化（暂时用内存，重启会丢）
checkpointer = MemorySaver()
travel_graph = build_travel_graph().compile(checkpointer=checkpointer)


@app.post("/workflow/run")
async def run_logic(
        thread_id: str = Body(None, description="会话ID，不传则新建"),
        initial_input: Dict[str, Any] = Body(None, description="初始输入数据"),
        resume_value: Any = Body(None, description="中断恢复时传回的值")
):
    # 如果没有 thread_id，生成一个，这是追踪用户进度的关键
    if not thread_id:
        thread_id = f"task-{uuid.uuid4().hex[:8]}"

    config = {"configurable": {"thread_id": thread_id}}

    # 2. 判断是【新开始】还是【恢复执行】
    if resume_value is not None:
        # 用户回复了中断请求（比如选了公司列表）
        result = travel_graph.invoke(Command(resume=resume_value), config=config)
    else:
        # 第一次启动流程
        result = travel_graph.invoke(initial_input, config=config)

    # 3. 检查当前状态是否被中断了
    snapshot = travel_graph.get_state(config)

    # 如果 snapshot.next 有值，说明还没跑完，卡在某个 interrupt 了
    if snapshot.next:
        # 获取中断的详细信息（就是你代码里 interrupt() 抛出的 payload）
        interrupt_content = snapshot.tasks[0].interrupts[0].value
        return {
            "thread_id": thread_id,
            "status": "NEED_INTERACTION",
            "interrupt_data": interrupt_content
        }

    # 4. 如果流程顺利走完了
    return {
        "thread_id": thread_id,
        "status": "COMPLETED",
        "final_result": result.get("itinerary", {}).get("final_report", "规划完成")
    }


if __name__ == "__main__":
    import uvicorn
    import os

    # 关键修改：云平台（Zeabur, Railway等）会通过环境变量 PORT 分配端口
    # 如果拿不到 PORT，则默认使用 8080 (Zeabur 默认检测端口)
    port = int(os.environ.get("PORT", 8080))
    
    # host 必须是 0.0.0.0 才能让外部访问
    uvicorn.run(app, host="0.0.0.0", port=port)
