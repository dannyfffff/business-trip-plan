#llm_agent.py
from datetime import timedelta, datetime
import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from typing import Union, List, Dict, Optional, Any
from config import deepseek_chat, PRE_MEETING_BUFFER_MINUTES, qwen_max
from data_models import UserInputParams, SelectedTransport, CompanyRecommendations
from prompts import INPUT_EXTRACTION_PROMPT, TRANSPORT_DECISION_PROMPT, day_1_plan_prompt, ENSURE_ADDRESS_PROMPT
from state import ItineraryItem, FixedEvent
from tools.travel_api import amap_geocode


def parse_user_input(user_input: str) -> Union[UserInputParams, dict]:
    """
    使用 LLM 将非结构化文本解析为结构化输入参数 (支持多固定事务 fixed_events)。
    返回 UserInputParams 实例的字典形式，解析失败时返回错误信息。
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", INPUT_EXTRACTION_PROMPT),
            ("user", user_input),
        ]
    )

    # 构建结构化输出链
    extraction_chain = prompt | deepseek_chat.with_structured_output(UserInputParams)

    try:
        # 执行解析
        result_model = extraction_chain.invoke({"user_input": user_input})

        # 返回字典形式，方便后续 LangGraph 状态合并
        return result_model.model_dump()

    except Exception as e:
        # 解析失败，返回错误信息及原始输入
        return {
            "error_message": f"LLM 结构化解析失败: {e}",
            "raw_input": user_input
        }


def llm_choose_transport(
    transport_options: List[Dict],
    user_params: Dict,
    arrival_commute_minutes: float,
    anchor_event_start: datetime,
) -> Optional[Dict[str, Any]]:
    """
    使用 LLM 在候选交通方案中选择最优班次
    """
    chain = (
        TRANSPORT_DECISION_PROMPT
        | qwen_max
        | JsonOutputParser(pydantic_object=SelectedTransport)
    )

    try:
        total_buffer_minutes = PRE_MEETING_BUFFER_MINUTES + arrival_commute_minutes
        latest_hub_arrival = anchor_event_start - timedelta(
            minutes=total_buffer_minutes
        )

        llm_input = {
            "transport_options": json.dumps(
                transport_options,
                ensure_ascii=False,
                indent=2
            ),
            "departure_date": user_params["departure_date"],
            "meeting_start_dt": anchor_event_start.strftime("%Y-%m-%d %H:%M"),
            "latest_hub_arrival": latest_hub_arrival.strftime("%Y-%m-%d %H:%M"),
            "arrival_commute_minutes": arrival_commute_minutes,
        }

        raw_output = chain.invoke(llm_input)

        if isinstance(raw_output, dict):
            selected_id = raw_output.get("id")
            selected_type = raw_output.get("type")

            return next(
                (
                    opt for opt in transport_options
                    if opt.get("id") == selected_id
                    and opt.get("type") == selected_type
                ),
                None
            )

        return None

    except Exception as e:
        print(f"❌ LLM 决策失败: {e}")
        return None


def to_json_serializable(obj):
    if isinstance(obj, datetime):
        return obj.strftime("%Y-%m-%d %H:%M")
    raise TypeError(f"Type {type(obj)} not serializable")

def generate_day1_tasks_for_llm(
    transport_item: ItineraryItem,
    fixed_events: List[FixedEvent],
    user_params: Dict[str, Any],
    day1_commute_matrix:  dict[str, dict[str, float]]
) -> List[ItineraryItem]:
    """
    将 Day 1 的交通段和固定事务交给 LLM 生成完整行程
    """

    # =====================
    # 1️⃣ 构造 LLM 输入
    # =====================

    prompt = day_1_plan_prompt.format(
        arrival_transport=json.dumps(transport_item, ensure_ascii=False, indent=2, default=to_json_serializable),
        day1_fixed_events=json.dumps(fixed_events, ensure_ascii=False, indent=2, default=to_json_serializable),
        user_params=json.dumps(user_params, ensure_ascii=False, indent=2, default=to_json_serializable),
        day1_commute_matrix=json.dumps(day1_commute_matrix, ensure_ascii=False, indent=2)
    )

    # =====================
    # 2️⃣ 调用 LLM
    # =====================
    try:
        raw_message = deepseek_chat.invoke(prompt)
        print(raw_message)
        print(type(raw_message))

        raw_output = raw_message.content

    except Exception as e:
        print(f"❌ LLM 生成 Day 1 行程失败: {e}")
        return []

    # =====================
    # 3️⃣ 解析 JSON 输出
    # =====================
    try:
        day_1_itinerary: List[ItineraryItem] = json.loads(raw_output)
    except Exception as e:
        print(f"❌ Day 1 行程 JSON 解析失败: {e}")
        return []

    return day_1_itinerary


# def generate_company_recommendations_by_llm(city: str) -> List[List[str]]:
#     """
#     根据城市推荐三组、每组三家企业用于调研。
#     """
#     try:
#         structured_llm = qwen_max.with_structured_output(CompanyRecommendations)
#
#         system_prompt = (
#             "你是一名专业的商务调研分析师。你的任务是根据给定的城市，推荐三组（Group A, B, C）"
#             "有价值、有影响力的科技企业进行会前调研。每组必须严格包含三家企业名称，企业必须真实存在"
#             "请严格按照提供的 JSON 格式输出结果。"
#         )
#         human_prompt = f"请为目标城市【{city}】推荐三组调研企业。"
#
#         messages = [
#             SystemMessage(content=system_prompt),
#             HumanMessage(content=human_prompt)
#         ]
#
#         result: CompanyRecommendations = structured_llm.invoke(messages)
#
#         # 🚨 修复 1: 检查 invoke 结果是否为 None
#         if result is None:
#             raise ValueError("LLM 调用失败或返回空结果 (None)")
#
#         recommendations = [group.companies for group in result.recommendation_groups]
#
#         # 严格校验格式
#         if len(recommendations) == 3 and all(len(g) == 3 for g in recommendations):
#             return recommendations
#
#         # 🚨 修复 2: 如果格式不规范（例如，列表数量不对），也抛出异常
#         raise ValueError(f"LLM 输出的推荐列表格式不符要求: {recommendations}")
#
#     except Exception as e:
#         print(f"LLM 推荐失败或格式错误: {e}")
#         # 在异常情况下，返回三个空列表，而不是依赖函数末尾的 return
#         return [[], [], []]

def generate_company_recommendations_by_llm(city: str) -> List[str]:
    """
    根据城市推荐知名企业供用户自由勾选。
    """
    try:
        # 修改提示词，要求生成一个长列表
        system_prompt = (
            f"你是一名专业的商务调研分析师。请为城市【{city}】推荐 15 家有价值的知名科技或核心企业。"
            "这些企业应适合商务访问或调研。请仅输出企业名称，不要包含其他解释，企业必须真实存在。"
        )

        # 假设你已经定义了相应的 Pydantic 模型来接收 List[str]
        # 如果没有，可以使用简单的字符串解析
        messages = [SystemMessage(content=system_prompt)]
        result = qwen_max.invoke(messages).content

        # 简单的解析逻辑（按行或逗号分割）
        companies = [c.strip() for c in result.replace("、", ",").replace("\n", ",").split(",") if c.strip()]
        return companies[:15]  # 确保数量适中

    except Exception as e:
        print(f"LLM 推荐失败: {e}")
        return ["腾讯", "华为", "大疆", "比亚迪", "平安科技"]


def geocode_company_by_name(company_name: str, city: str) -> Dict[str, Any] | None:

    prompt = ENSURE_ADDRESS_PROMPT.format(
        company_name=company_name,
        city=city
    )

    try:
        address = qwen_max.invoke(prompt).content.strip()
        if not address:
            return None

        geo = amap_geocode(address=address, city=city)
        if not geo:
            return None

        return {
            "address": address,
            "lat": geo["lat"],
            "lon": geo["lon"]
        }


    except KeyError as e:
        raise

