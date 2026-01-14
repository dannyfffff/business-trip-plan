from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid

# 导入你现有的 LangGraph 编译对象和状态定义
from graph import build_travel_graph
from langgraph.checkpoint.memory import MemorySaver

app_fastapi = FastAPI(title="LangGraph Travel API")

# 初始化 LangGraph
checkpointer = MemorySaver()
langgraph_app = build_travel_graph().compile(checkpointer=checkpointer)


# 定义请求体结构
class PlanningRequest(BaseModel):
    thread_id: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    resume_value: Optional[Any] = None


@app_fastapi.post("/run")
async def run_workflow(req: PlanningRequest):
    # 如果没有提供 thread_id，则生成一个新的
    thread_id = req.thread_id or f"api-{uuid.uuid4().hex}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        if req.resume_value is not None:
            # 恢复中断的流程
            from langgraph.types import Command
            result = langgraph_app.invoke(Command(resume=req.resume_value), config=config)
        else:
            # 启动新流程
            result = langgraph_app.invoke(req.input_data, config=config)

        # 检查是否遇到了中断
        is_interrupt = "__interrupt__" in result

        return {
            "thread_id": thread_id,
            "status": "interrupted" if is_interrupt else "completed",
            "data": result,
            "interrupt_info": result.get("__interrupt__") if is_interrupt else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app_fastapi, host="0.0.0.0", port=8000)