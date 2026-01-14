import streamlit as st
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
import uuid
import json
from typing import Dict, Any, Optional, Literal, Union

# 确保导入了所有依赖项，路径正确
# 假设这些文件都在同一目录下或已正确配置 PYTHONPATH
from graph import build_travel_graph
# 导入状态类型，用于类型提示和初始化
from state import TravelPlanState, UserContext, LocationContext, TransportContext, CompanyContext, ItineraryContext, \
    ControlContext

# --- 1. 初始化和配置 ---
st.set_page_config(page_title="✈️ 商务行程规划助手", layout="wide")


# LangGraph 配置：使用 @st.cache_resource 确保图只编译一次
@st.cache_resource
def get_graph():
    """初始化 LangGraph 并返回编译后的应用。"""
    # 使用 MemorySaver 作为检查点，实现会话记忆
    checkpointer = MemorySaver()
    return build_travel_graph().compile(checkpointer=checkpointer)


# 全局变量
app = get_graph()
CONFIG = {}


# --- 2. 状态管理和流程驱动函数 ---

def initialize_session():
    """初始化 Streamlit session_state。"""
    # 确保每个用户会话都有一个唯一的线程 ID
    if 'thread_id' not in st.session_state:
        st.session_state.thread_id = f"st-plan-{uuid.uuid4().hex}"
        # LangGraph 需要的配置，用于 Checkpointer
        st.session_state.config = {"configurable": {"thread_id": st.session_state.thread_id}}

    # 初始化 UI 状态
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'state' not in st.session_state:
        st.session_state.state: Optional[TravelPlanState] = None
    if 'status' not in st.session_state:
        st.session_state.status = "Initialized"

    global CONFIG
    CONFIG = st.session_state.config


def run_workflow_step(input_data: Optional[Dict[str, Any]] = None,
                      resume_value: Optional[Union[bool, str, dict]] = None):
    """驱动 LangGraph 运行一个步骤，直到流程结束或遇到中断。"""
    st.session_state.status = "Running..."
    st.toast("正在计算下一步骤...", icon="⏳")

    # 记录日志
    if resume_value is not None:
        log_msg = f"➡️ 恢复流程，输入: {resume_value}"
    elif input_data is not None:
        log_msg = "➡️ 启动新流程"
    else:
        log_msg = "➡️ 启动/恢复流程（无输入）"

    st.session_state.messages.append(("System", log_msg))

    try:
        # LangGraph 驱动逻辑
        if resume_value is not None:
            # 流程中断后，使用 Command(resume=...) 传递恢复值
            input_for_graph = Command(resume=resume_value)
            result = app.invoke(input_for_graph, config=CONFIG)
        else:
            # 流程开始时，传入初始状态
            # 注意：app.invoke 要求传入一个字典，而不是 TypedDict 实例
            result = app.invoke(input_data, config=CONFIG)

        # 更新状态
        st.session_state.state = result
        st.session_state.status = "Paused for User Input" if "__interrupt__" in result else "Completed"

        # 强制 Streamlit 重新运行以更新 UI
        st.rerun()

    except Exception as e:
        # 捕获并显示错误
        st.error(f"LangGraph 运行错误: {e}")
        st.session_state.status = "Error"
        # 错误时，清空状态并重新加载输入表单
        st.session_state.state = None
        st.rerun()


def handle_start_planning(input_params: dict):
    """处理用户点击 '开始规划' 按钮的逻辑。"""

    # 💥 关键修改：将所有固定事件信息合并为一个字符串
    fixed_events_info = input_params['fixed_events_input']

    # 模拟用户输入，以便 LLM 抽取
    user_input_str = (
        f"规划 {input_params['origin_city']} 到 {input_params['destination_city']} 的行程。 "
        f"出发日期: {input_params['departure_date']}。 "
        f"出发地: {input_params['origin_address']}。 "
        f"酒店地址: {input_params['hotel_address']}。\n"
        f"--- 固定事件/会议列表 ---\n{fixed_events_info}\n"
    )

    # 模拟 UserInputParams 的结构
    parsed_params_data = {
        "origin_city": input_params['origin_city'],
        "destination_city": input_params['destination_city'],
        "departure_date": input_params['departure_date'],
        "home_address": input_params['origin_address'],
        "hotel_address": input_params['hotel_address'],
        # 💥 关键修改：将 fixed_events 设置为空列表，等待 'check_constraints' 节点通过 LLM 解析 user_input_str 来填充
        "fixed_events": []
    }

    # 构造 TravelPlanState 必须的所有字段
    initial_state: TravelPlanState = {
        "user": UserContext(
            raw_input=user_input_str,
            parsed_params=parsed_params_data,
        ),
        "locations": LocationContext(
            home=None,
            hotel=None
        ),
        "transport": TransportContext(
            flight_options=[],
            train_options=[],
            selected_index=None,
            selected_option_raw=None,
            selected_transport=None,
            approved=None,
        ),
        "companies": CompanyContext(
            target_names=[],
            candidates=[],
        ),
        "itinerary": ItineraryContext(
            # 💥 关键修改：这里必须是空列表，否则 check_constraints 无法识别。
            # check_constraints 节点将通过 LLM 解析 raw_input 来获取 fixed_events 列表
            fixed_events=[],
            day_1=None,
            day_2=None,
            day_3=None,
            final_itinerary=[],
            final_report="",
        ),
        "control": ControlContext(
            error_message=None,
            refinement_instruction=None,
        )
    }

    # 初始化 session 并启动流程
    initialize_session()
    st.session_state.status = "Starting..."
    st.session_state.messages = []
    st.session_state.messages.append(("System", "结构化输入已获取，开始 LangGraph 流程."))

    # 传入 LangGraph 的是字典，而非 TypedDict
    run_workflow_step(input_data=dict(initial_state))


# --- 3. UI 元素和交互处理 ---

def render_interruption_ui(interrupt_data):
    """根据中断类型渲染不同的用户交互界面"""
    # LangGraph 中断数据结构：[Command(interrupt={'node_name':..., 'value':...})]
    payload = interrupt_data[0].value

    # --- 1. 审批中断 (approval) ---
    if payload["type"] == "approval":
        st.subheader("✅ 交通方案推荐：请审批")
        st.info(payload["message"])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("同意该交通方案", key="approve_btn", type="primary"):
                run_workflow_step(resume_value=True)
        with col2:
            if st.button("选择其他交通方案", key="reject_btn"):
                run_workflow_step(resume_value=False)

    # --- 2. 手动选择中断 (select_transport) ---
    elif payload["type"] == "select_transport":
        st.subheader("📋 请手动选择一个交通方案")

        # ⚠️ 从 payload 中直接获取 options
        display_options = payload.get("options", [])

        if not display_options:
            st.warning("⚠️ 交通选项不足，无法继续规划。")
            if st.button("返回主页 / 重新输入", key="reset_page"):
                st.session_state.state = None
                st.rerun()
            return

        # 将 [0] [1] 等前缀去除，以提供更美观的展示，但 radio 的索引仍是 0, 1, 2...
        radio_options = [desc.split('] ', 1)[1] if desc.startswith('[') else desc for desc in display_options]

        selected_desc = st.radio(
            "选择方案：", options=radio_options, index=0, key="manual_select_radio"
        )

        # 找到被选中的方案在原始列表中的索引
        chosen_index = radio_options.index(selected_desc)

        # 💥 关键：传递给 LangGraph 的是用户选择的索引号
        # 注意：这里的 chosen_index 是 0-based index，它对应于 `user_select_transport` 节点中的 `selectable_options` 列表
        if st.button("确认选择", key="confirm_select_btn", type="primary"):
            # `user_select_transport` 节点需要的是用户输入的索引数字（字符串）
            # 这里的索引是 `selectable_options` 中的索引
            run_workflow_step(resume_value=str(chosen_index))

    # 🚀 --- 3. 调研模式选择 (research_mode_selection) ---
    elif payload["type"] == "research_mode_selection":
        st.subheader("🏢 请选择会议前调研模式")
        st.info("您希望如何安排会议前的行程？")

        # 用户的选择值需要对应 LangGraph 节点返回的 Command 结构
        mode_options = {
            "自定义调研": "1",  # 💥 关键：改为节点预期的输入值
            "自动推荐": "2",  # 💥 关键：改为节点预期的输入值
            "跳过调研": "3"  # 💥 关键：改为节点预期的输入值
        }

        # 调整 radio 的 options，让用户界面更友好
        display_modes = list(mode_options.keys())

        selected_mode_desc = st.radio(
            "选择模式：",
            options=display_modes,
            index=1,
            key="research_mode_radio"
        )

        custom_input = ""
        # 使用 mode_options[selected_mode_desc] 获取目标 ID (1, 2, 3)
        selected_mode_id = mode_options[selected_mode_desc]

        if selected_mode_id == "1":  # 自定义调研
            custom_input = st.text_input(
                "请输入公司名称 (用逗号分隔，例: 华为,腾讯):",
                key="custom_companies_input"
            )

        if st.button("确认调研模式", key="confirm_research_btn", type="primary"):

            if selected_mode_id == "1":
                if not custom_input.strip():
                    st.warning("请输入至少一个公司名称进行自定义调研。")
                    return
                # 💥 修复逻辑: 传递给节点期望的格式 '1:公司A,公司B'
                resume_value = f"{selected_mode_id}:{custom_input.strip()}"
            else:
                # 💥 修复逻辑: 对于自动推荐(2)和跳过(3)，只传递对应的数字字符串
                resume_value = selected_mode_id

            # 统一启动流程
            run_workflow_step(resume_value=resume_value)

    # 🔄 --- 4. 行程修改/再规划 (refine_itinerary) ---
    elif payload["type"] == "refine_itinerary":
        st.subheader("📝 行程优化与修改")
        st.warning("您可以在下方提出任何修改要求 (例如：'将 Day 2 的活动 A 提前 1 小时')。")

        # 获取当前图的状态值，以展示 Markdown 报告
        current_values: TravelPlanState = app.get_state(CONFIG).values
        markdown_report = current_values.get("itinerary", {}).get("final_report")

        if markdown_report:
            st.markdown("### 🗓️ 当前规划行程概览")
            with st.container(border=True):
                st.markdown(markdown_report)
        else:
            st.info("无法加载当前行程报告。")

        # 从 payload 消息中提取 JSON（如果需要）
        # 注意: 这里的 'message' 键是上一个问题中修复的，用于展示原始数据
        message_parts = payload["message"].split("【当前行程】\n", 1)
        if len(message_parts) > 1:
            with st.expander("🔍 点击查看原始数据结构 (JSON)"):
                st.code(message_parts[1].strip(), language='json')

        user_instruction = st.text_input(
            "请输入您的修改要求:",
            key="refinement_instruction_input"
        )

        col_submit, col_finish = st.columns([1, 1])

        with col_submit:
            if st.button("提交修改要求", key="submit_refinement_btn", type="primary"):
                if user_instruction.strip():
                    # 传回修改指令，触发再规划
                    run_workflow_step(resume_value=user_instruction)
                else:
                    st.warning("请输入修改指令或点击 '结束流程'。")

        with col_finish:
            if st.button("结束修改流程并完成报告", key="finish_refinement_btn"):
                # 传回空字符串， LangGraph 节点会识别为无修改并结束循环
                run_workflow_step(resume_value="")

    # 🚀 --- 5. 企业选择 (company_selection) ---
    # elif payload["type"] == "company_selection":
    #     st.subheader("🏢 请选择一组调研企业")
    #     st.info(payload.get("title", "请从以下方案中选择一组企业进行调研："))
    #
    #     options = payload.get("options", [])
    #
    #     # 格式化选项供 Streamlit Radio 展示
    #     display_options = {}
    #     for item in options:
    #         index = item["index"]
    #         companies = item["companies"]
    #         # 这里的 index 是 0, 1, 2...
    #         display_key = f"方案 {index + 1}: {', '.join(companies)}"
    #         display_options[display_key] = index  # 存储 index 作为值
    #
    #     # Streamlit radio 选择
    #     selected_desc = st.radio(
    #         "选择方案：",
    #         options=list(display_options.keys()),
    #         index=0,  # 默认选择方案 1
    #         key="company_selection_radio"
    #     )
    #
    #     if st.button("确认选择企业", key="confirm_company_select_btn", type="primary"):
    #         # 获取用户选择的索引号 (0, 1, 2...)
    #         selected_index = display_options[selected_desc]
    #
    #         # 💥 关键：将索引号（字符串形式）传回 LangGraph
    #         # 对应 auto_research 节点的 selected_index = interrupt(...)
    #         run_workflow_step(resume_value=str(selected_index))

    elif payload["type"] == "company_multi_selection":
        st.subheader("🏢 企业调研自主筛选")
        st.info(payload.get("title", "为您找到以下推荐企业，请勾选您感兴趣的（建议 3-5 家）："))

        candidates = payload.get("options", [])

        if not candidates:
            st.warning("⚠️ 未找到推荐企业，请尝试手动输入或跳过。")
            if st.button("返回"): run_workflow_step(resume_value=[])
        else:
            # 使用 Streamlit 的多选组件
            selected_list = st.multiselect(
                "请勾选目标企业：",
                options=candidates,
                default=candidates[:2] if len(candidates) > 2 else []  # 默认勾选前两家
            )

            st.markdown("---")
            if st.button("确认选择并生成行程", key="confirm_multi_company_btn", type="primary"):
                if not selected_list:
                    st.warning("请至少选择一家企业！")
                else:
                    run_workflow_step(resume_value=selected_list)
    # --- 6. 未知中断类型 ---
    else:
        st.error(f"发现未知中断类型: {payload['type']}")


def render_completed_report(state: Dict[str, Any]):
    """流程完成后，渲染最终的报告"""
    st.balloons()
    st.subheader("🎉 商务行程规划完成")

    # 💥 修正：从 state['itinerary']['final_report'] 获取报告
    final_report = state.get('itinerary', {}).get('final_report')

    if final_report:
        st.markdown(final_report)
    else:
        st.warning("最终报告内容为空。请检查 LangGraph 运行日志。")

    if st.button("重新规划", key="reset_app_btn"):
        st.session_state.state = None
        st.session_state.status = "Initialized"
        st.rerun()


def render_input_form():
    """渲染结构化输入表单"""
    st.title("✈️ 智能商务行程规划助手")

    # 使用 st.form 确保所有输入在点击按钮时才提交
    with st.form("travel_form"):
        st.header("1. 基础行程信息")

        col1, col2, col_date = st.columns(3)
        with col1:
            origin_city = st.text_input("出发城市 (例: 上海)", value="上海", key="origin_city")
        with col2:
            destination_city = st.text_input("目的城市 (例: 深圳)", value="深圳", key="destination_city")
        with col_date:
            departure_date = st.text_input("出发日期 (格式: YYYY-MM-DD, 例: 2026-01-14)",
                                           key="departure_date",
                                           value="2026-01-25")

        origin_address = st.text_input("出发地点 (详细地址，例: 上海市浦东新区川沙新镇黄赵路310号)",
                                       key="origin_address",
                                       value="上海市浦东新区川沙新镇黄赵路310号")

        st.markdown("---")
        st.header("2. 住宿信息")

        hotel_address = st.text_input("酒店地点 (详细地址，例: 深圳市南山区西丽街道官龙村西82号)",
                                      key="hotel_address",
                                      value="深圳市南山区西丽街道官龙村西82号")

        st.markdown("---")
        st.header("3. 固定事件/会议信息 (支持多个)")

        # 💥 关键修改：使用 st.text_area 接收多事件信息
        fixed_events_input = st.text_area(
            "请输入所有会议和固定事件（每行一个，格式例如：\n"
            "会议：深圳南山桃园路2号，2026-01-15 16:00，持续1小时\n"
            "晚宴：福田中心大厦，2026-01-15 19:30，持续2小时）",
            key="fixed_events_input",
            height=150,
            value=(
                "商务会议：深圳市南山区深南大道10000号，2026-01-26 16:00，持续1小时\n"
                "晚餐：深圳市南山区桃园路2号，2026-01-27 19:30，持续90分钟"
            )
        )

        submitted = st.form_submit_button("🚀 开始规划", type="primary")

        if submitted:
            # 从 session_state 中获取所有输入 (st.form 的标准做法)
            input_params = {
                "origin_city": st.session_state.origin_city,
                "origin_address": st.session_state.origin_address,
                "destination_city": st.session_state.destination_city,
                "departure_date": st.session_state.departure_date,
                "fixed_events_input": st.session_state.fixed_events_input,  # 新增
                "hotel_address": st.session_state.hotel_address,
            }
            # 校验空值
            required_fields = ['origin_city', 'origin_address', 'destination_city', 'departure_date',
                               'fixed_events_input', 'hotel_address']

            field_names = {
                'origin_city': '出发城市', 'origin_address': '出发地点',
                'destination_city': '目的城市', 'departure_date': '出发日期',
                'fixed_events_input': '固定事件/会议',
                'hotel_address': '酒店地点'
            }

            for field in required_fields:
                if not input_params.get(field) or not str(input_params[field]).strip():
                    st.warning(f"⚠️ **{field_names.get(field, field)}** 字段不能为空，请完整填写所有信息！")
                    return

            # 所有校验通过，开始规划
            handle_start_planning(input_params)


def main():
    initialize_session()

    # 在侧边栏显示流程状态，保持简洁
    with st.sidebar:
        st.header("流程状态")
        st.markdown(f"**状态:** `{st.session_state.status}`")
        if 'thread_id' in st.session_state:
            st.markdown(f"**Thread ID:** `{st.session_state.thread_id[:8]}...`")

        # 流程日志（可选）
        if st.toggle("显示流程日志", value=False):
            st.markdown("---")
            st.subheader("日志记录")
            for source, msg in reversed(st.session_state.messages):
                st.markdown(f"> **{source}**: {msg}")

    current_state = st.session_state.state

    if current_state is None or st.session_state.status == "Initialized" or st.session_state.status == "Error":
        # 如果是首次加载、初始化状态或发生错误，渲染输入表单
        render_input_form()
        return

    # --- 流程驱动和结果展示 ---

    # 1. 中断
    if "__interrupt__" in current_state:
        # 流程暂停，显示交互 UI
        st.sidebar.markdown("**🔴 流程暂停，需人工干预**")
        render_interruption_ui(current_state["__interrupt__"])

    # 2. 完成
    # 💥 修正：判断流程完成以 `control` 状态或 `itinerary.final_report` 为准
    elif st.session_state.status == "Completed" or current_state.get('itinerary', {}).get('final_report'):
        # 流程完成，显示最终报告
        render_completed_report(current_state)

    # 3. 错误
    elif current_state.get('control', {}).get('error_message'):
        # 流程因错误终止
        st.error(f"规划流程因错误终止：{current_state['control']['error_message']}")

    # 4. 运行中
    elif st.session_state.status == "Running...":
        # 流程正在运行中，显示加载提示
        st.info("LangGraph 正在后台运行，请等待...")
        st.progress(0.7, text="正在进行交通查询、地理编码或LLM规划...")

    # 5. 兜底
    else:
        st.info("流程已启动，正在等待 LangGraph 返回下一步结果或中断。")


if __name__ == "__main__":
    main()