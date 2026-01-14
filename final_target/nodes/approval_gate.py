#approval_gate.py
from state import TravelPlanState
from langgraph.types import interrupt, Command
from typing import Literal
from langgraph.graph import END


def transport_approval_gate(state: TravelPlanState) -> Command[Literal["plan_day_1_by_llm", "user_select_transport"]]:
    """
    节点 4.5: 交通方案人工审批门。
    检查用户是否已审批。如果未审批，则暂停流程。
    """
    selected_transport = state.get("transport", {}).get("selected_option_raw")

    if not selected_transport:
        print("⚠️ 审批门发现 LLM 未选定方案，跳过审批。")
        return Command(goto="user_select_transport")

    payload = {
        "type": "approval",
        "message": (
            f"推荐交通方案：{selected_transport.get('type', '交通')} {selected_transport.get('id', 'N/A')}\n"
            f"  - 出发: {selected_transport.get('departure_time', 'N/A')} (从 {selected_transport.get('departure_hub_name', 'N/A')})\n"
            f"  - 抵达: {selected_transport.get('arrival_time', 'N/A')} (到 {selected_transport.get('arrival_hub_name', 'N/A')})\n"
            "\n"
            "**请确认是否采纳此方案？** 请输入 **是** 或 **否**。\n"
        )
    }

    decision_raw = interrupt(payload)

    # 🚨 修复开始：直接检查布尔值或匹配相应的字符串
    is_approved = False

    # 1. 检查布尔值 (来自 Streamlit 按钮)
    if decision_raw is True:
        is_approved = True
    elif decision_raw is False:
        is_approved = False

    # 2. 检查字符串输入 (兜底或用户直接输入文本)
    elif isinstance(decision_raw, str):
        decision_str = decision_raw.strip().lower()
        if decision_str in ["是", "y", "yes", "true"]:
            is_approved = True
        elif decision_str in ["否", "n", "no", "false"]:
            is_approved = False
    # 🚨 修复结束

    # 3. 根据解析结果跳转
    if is_approved:
        print("✅ 用户确认交通方案，进入 Day 1 规划。")
        return Command(goto="plan_day_1_by_llm")
    else:
        print("❌ 用户否决交通方案，返回重新选择。")
        return Command(goto="user_select_transport")



def user_select_research_mode(state: TravelPlanState) -> Command[Literal["custom_research", "auto_research", "skip_research"]]:
    """
    节点 4.8: 用户选择调研模式：自定义调研、自动推荐调研还是跳过。
    """
    print("\n--- ⏱️ 节点 4.8: 用户选择调研模式 ---")

    payload = {
        "type": "research_mode_selection",
        "message": (
            "🚀 **是否进行会议前企业调研规划？**\n"
            "请选择调研模式：\n"
            "  1️⃣ 自定义调研：输入 `1: 华为, 腾讯`\n"
            "  2️⃣ 智能自动调研：输入 `2`\n"
            "  3️⃣ 跳过调研：输入 `3`\n"
        )
    }

    decision = interrupt(payload)
    decision_str = str(decision).strip().replace("：", ":")

    # =========================
    # 1️⃣ 自定义调研 (1 / 1:xxx)
    # =========================
    if decision_str.startswith("1"):
        company_part = ""

        # 允许 1:xxx 或 1 xxx
        if ":" in decision_str:
            company_part = decision_str.split(":", 1)[1]
        else:
            company_part = decision_str[1:]

        company_part = company_part.strip()

        # 统一分隔符
        company_part = company_part.replace("，", ",")
        company_part = company_part.strip(",")

        import re
        companies = [
            name.strip()
            for name in re.split(r"[,\s]+", company_part)
            if name.strip()
        ]

        if companies:
            print(f"✅ 用户选择自定义调研，目标企业: {', '.join(companies)}")
            return Command(
                update={
                    "companies":{
                                "target_names": companies
                            }
                        },
                goto="custom_research"
            )

        print("⚠️ 用户选择自定义调研但未提供企业名称，进入 custom_research（可二次补充）")
        return Command(goto="custom_research")

    # =========================
    # 2️⃣ 自动调研
    # =========================
    if decision_str == "2":
        print("🤖 用户选择智能自动调研")
        return Command(goto="auto_research")

    # =========================
    # 3️⃣ 跳过调研
    # =========================
    if decision_str == "3":
        print("⏭️ 用户选择跳过调研")
        return Command(goto="skip_research")

    # =========================
    # 4️⃣ 非法输入兜底
    # =========================
    print(f"❌ 无法识别输入: {decision_str}，默认跳过调研")
    return Command(goto="skip_research")



def user_refine_itinerary(state: TravelPlanState) -> Command[Literal["build_final_itinerary_and_report", END]]:
    """
    询问用户是否需要修改最终行程
    """
    print("\n--- 🔁 节点: user_refine_itinerary ---")

    itinerary = state["itinerary"]
    control = state.setdefault("control", {})

    final_report = itinerary.get("final_report", "")

    user_input = interrupt({
        "type": "refine_itinerary",
        "final_report": final_report,
        "message": "是否需要修改行程？如果需要，请输入修改要求；不需要请直接确认。"
    })

    # ===== 用户确认：不需要修改 =====
    if not user_input or not user_input.strip():
        print("✅ 用户确认无需修改，流程结束")
        control["refinement_instruction"] = None
        return Command(goto=END)

    # ===== 用户提出修改 =====
    instruction = user_input.strip()
    print(f"✏️ 用户修改要求: {instruction}")
    control["refinement_instruction"] = instruction

    return Command(
        goto="build_final_itinerary_and_report",
        update={
            "control":control
        }
    )
