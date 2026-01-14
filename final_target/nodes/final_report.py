#final_report.py
from config import deepseek_chat
from llm_agent import generate_day1_tasks_for_llm, to_json_serializable
from prompts import DAY_2_3_PLAN_PROMPT, FINAL_ITINERARY_TABLE_PROMPT, FINAL_ITINERARY_REFINE_PROMPT
from state import TravelPlanState, ItineraryItem, FixedEvent
from typing import Dict, Any
from datetime import datetime, timedelta
from typing import List
import json
from tools.travel_api import amap_geocode, generate_day1_commute_matrix, generate_day23_commute_matrix


def plan_day_1_by_llm(state: TravelPlanState) -> Dict[str, Any]:
    """
    节点 5（Day 1 LLM 行程规划）：
    - 将已选交通方案 selected_option_raw 转换为 ItineraryItem
    - 判断 Day 1 是否存在固定事务
    - 调用 generate_day1_tasks_for_llm 生成 Day 1 完整行程
    """

    print("\n--- ⏱️ 节点 5: Day 1 LLM 行程规划 ---")

    transport_ctx = state["transport"]
    user_ctx = state["user"]
    hotel_loc = state["locations"]["hotel"]

    selected_raw = transport_ctx.get("selected_option_raw")
    if not selected_raw:
        return {
            "control": {
                "error_message": "未选定交通方案，无法进行 Day 1 行程规划"
            }
        }

    user_params = user_ctx["parsed_params"]
    fixed_events = user_params.get("fixed_events", [])

    # ========= 1️⃣ 解析交通时间 =========
    try:
        departure_date = selected_raw["departure_date"]
        arrival_date = selected_raw["arrival_date"]
        dep_time_str = selected_raw["departure_time"]
        arr_time_str = selected_raw["arrival_time"]

        start_dt = datetime.strptime(
            f"{departure_date} {dep_time_str}", "%Y-%m-%d %H:%M"
        )
        end_dt = datetime.strptime(
            f"{arrival_date} {arr_time_str}", "%Y-%m-%d %H:%M"
        )

    except Exception as e:
        return {
            "control": {
                "error_message": f"交通时间解析失败: {e}"
            }
        }

    # ========= 2️⃣ 构造主交通 ItineraryItem =========
    arr_hub_name = selected_raw.get("arrival_hub_name")
    arr_hub_city = user_params["destination_city"]
    arr_hub_coords = amap_geocode(arr_hub_name, arr_hub_city)
    if not arr_hub_coords and not arr_hub_name.endswith('站'):   # 防止出现 上海 （api自动忽略站这个字）的情况
        arr_hub_coords = amap_geocode(f"{arr_hub_name}站", arr_hub_city)
    if not arr_hub_coords:
        return {
            "control": {
                "error_message": "交通精确计算失败：无法对选定班次的枢纽进行地理编码。"
        }}

    transport_item: ItineraryItem = {
        "type": "transport",
        "description": (
            f"{selected_raw.get('type')} {selected_raw.get('id')} "
            f"({selected_raw.get('departure_hub_name')} → {selected_raw.get('arrival_hub_name')})"
        ),
        "start_time": start_dt,
        "end_time": end_dt,
        "location": {
            "city": user_params["destination_city"],
            "address": selected_raw.get("arrival_hub_name"),
            "name": selected_raw.get("arrival_hub_name"),
            "lat": arr_hub_coords.get("lat"),
            "lon": arr_hub_coords.get("lon"),
        },
        "details": {
            "raw_option": selected_raw,
            "price": selected_raw.get("price"),
            "duration": selected_raw.get("duration"),
        }
    }


    # ========= 3️⃣ Day 1 固定事务 =========
    day1_events = sorted(
        [
            e for e in fixed_events
            if e["start_time"].date() == end_dt.date()
        ],
        key=lambda e: e["start_time"]
    )

    earliest_day1_event = day1_events[0] if day1_events else None

    print(
        f"   -> Day 1 是否存在固定事务: {'是' if earliest_day1_event else '否'}"
    )

    day1_commute_matrix = generate_day1_commute_matrix(
        transport_item=transport_item,
        day1_events=day1_events,
        hotel_loc=hotel_loc
    )

    # ========= 4️⃣ 调用 LLM 生成 Day 1 行程 =========
    day_1_itinerary: List[ItineraryItem] = generate_day1_tasks_for_llm(
        transport_item=transport_item,
        fixed_events=day1_events,
        user_params=user_params,
        day1_commute_matrix=day1_commute_matrix,
    )

    print(f"   -> Day 1 LLM 行程生成完成，共 {len(day_1_itinerary)} 条任务")


    # ========= 5️⃣ 写回 state =========
    return {
        "transport": {
            **transport_ctx,
            "selected_transport": transport_item
        },
        "itinerary": {
            "fixed_events": fixed_events,
            "day_1": day_1_itinerary
        },
        "control": {
            "error_message": None
        }
    }



def plan_day_2_3_by_llm(state: TravelPlanState) -> Dict[str, Any]:
    """
    根据待调研企业和固定事件，使用 LLM 生成 Day 2 和 Day 3 完整行程
    """
    print("\n--- ⏱️ 节点: plan_day_2_3_by_llm ---")

    origin_itinerary_ctx = state["itinerary"]
    user_params = state["user"]["parsed_params"]
    hotel_loc = state["locations"]["hotel"]
    fixed_events: List[FixedEvent] = state["itinerary"]["fixed_events"]
    companies_ctx = state.get("companies", {})
    companies_to_plan = companies_ctx.get("candidates", [])

    # Day2 / Day3 日期
    day_1_date = datetime.strptime(user_params.get("departure_date"), "%Y-%m-%d").date()
    day_2_date = day_1_date + timedelta(days=1)
    day_3_date = day_1_date + timedelta(days=2)

    # 筛选固定事件
    day_2_events = [
        e for e in fixed_events if e["start_time"].date() == day_2_date
    ]
    day_3_events = [
        e for e in fixed_events if e["start_time"].date() == day_3_date
    ]


    try:
        day_2_3_commute_matrix = generate_day23_commute_matrix(
                day2_events=day_2_events,
                day3_events=day_3_events,
                companies_to_plan=companies_to_plan,
                hotel_loc=hotel_loc
        )
    except Exception as e:
        msg = f"❌ 计算 day_2_3_commute_matrix 失败: {e}"
        print(msg)
        return {
            "itinerary": {
                **origin_itinerary_ctx,
                "day_2": [],
                "day_3": []
            },
            "control": {
                "error_message": msg
            }
        }

    # 准备 LLM 输入 prompt
    serializable_companies = [
        company.model_dump()  # Pydantic v2 方法
        for company in companies_to_plan
    ]
    prompt = DAY_2_3_PLAN_PROMPT.format(
        day_2_events=json.dumps(day_2_events, ensure_ascii=False, indent=2, default=to_json_serializable),
        day_3_events=json.dumps(day_3_events, ensure_ascii=False, indent=2, default=to_json_serializable),
        companies_to_plan=json.dumps(serializable_companies,ensure_ascii=False,indent=2),
        user_params=json.dumps(user_params, ensure_ascii=False, indent=2, default=to_json_serializable),
        hotel=json.dumps(hotel_loc, ensure_ascii=False, indent=2, default=to_json_serializable),
        day_2_3_commute_matrix=json.dumps(day_2_3_commute_matrix, ensure_ascii=False)
    )

    # 调用 LLM
    try:
        raw_message = deepseek_chat.invoke(prompt)
        raw_output = raw_message.content
    except Exception as e:
        msg = f"❌ LLM 生成 Day 2/3 行程失败: {e}"
        print(msg)
        return {
            "itinerary": {
                **origin_itinerary_ctx,
                "day_2": [],
                "day_3": []
            },
            "control": {
                "error_message": msg
            }
        }

    # 解析 JSON 输出
    try:
        itinerary_items: List[ItineraryItem] = json.loads(raw_output)
    except Exception as e:
        msg = f"❌ Day 2/3 行程 JSON 解析失败: {e}"
        print(msg)
        return {
            "itinerary": {
                **origin_itinerary_ctx,
                "day_2": [],
                "day_3": []
            },
            "control": {
                "error_message": msg
            }
        }

    # 分 Day2 / Day3
    for item in itinerary_items:
        if isinstance(item.get("start_time"), str):
            item["start_time"] = datetime.strptime(item["start_time"], "%Y-%m-%d %H:%M")
        if isinstance(item.get("end_time"), str):
            item["end_time"] = datetime.strptime(item["end_time"], "%Y-%m-%d %H:%M")
    day_2_itinerary = [i for i in itinerary_items if i["start_time"].date() == day_2_date]
    day_3_itinerary = [i for i in itinerary_items if i["start_time"].date() == day_3_date]

    # 更新状态
    state["itinerary"]["day_2"] = day_2_itinerary
    state["itinerary"]["day_3"] = day_3_itinerary

    print(f"✅ Day 2 共 {len(day_2_itinerary)} 项, Day 3 共 {len(day_3_itinerary)} 项")

    return {
        "itinerary": {
            **origin_itinerary_ctx,
            "day_2": day_2_itinerary,
            "day_3": day_3_itinerary
        },
        "control": {
                "error_message": None
            }
    }




def build_final_itinerary_and_report(state: TravelPlanState) -> Dict[str, Any]:
    """
    合并 Day1 / Day2 / Day3 行程，
    根据是否存在用户修改意见，生成或重生成最终 Markdown 行程表
    """
    print("\n--- 📋 节点: build_final_itinerary_and_report ---")

    itinerary = state["itinerary"]
    control = state.setdefault("control", {})
    refine_instruction = control.get("refinement_instruction")

    # ========= 1️⃣ 合并前三天 =========
    all_items: List[ItineraryItem] = []

    for day_key in ("day_1", "day_2", "day_3"):
        day_items = itinerary.get(day_key)
        if day_items:
            all_items.extend(day_items)

    if not all_items:
        msg = "前三天行程为空，无法生成最终行程"
        print(f"❌ {msg}")
        return {
            "control": {
                "error_message": msg,
                "refinement_instruction": None
            }
        }

    # ========= 2️⃣ 统一时间类型并排序 =========
    for item in all_items:
        if isinstance(item.get("start_time"), str):
            item["start_time"] = datetime.strptime(
                item["start_time"], "%Y-%m-%d %H:%M"
            )
        if isinstance(item.get("end_time"), str):
            item["end_time"] = datetime.strptime(
                item["end_time"], "%Y-%m-%d %H:%M"
            )

    all_items.sort(key=lambda x: x["start_time"])
    itinerary["final_itinerary"] = all_items

    # ========= 3️⃣ 构造 Prompt =========
    if refine_instruction:
        print("✏️ 检测到用户修改意见，进行二次生成")
        prompt = FINAL_ITINERARY_REFINE_PROMPT.format(
            final_itinerary=json.dumps(
                all_items,
                ensure_ascii=False,
                indent=2,
                default=to_json_serializable
            ),
            refine_instruction=refine_instruction
        )
    else:
        print("🆕 首次生成最终行程表")
        prompt = FINAL_ITINERARY_TABLE_PROMPT.format(
            final_itinerary=json.dumps(
                all_items,
                ensure_ascii=False,
                indent=2,
                default=to_json_serializable
            )
        )

    # ========= 4️⃣ 调用 LLM =========
    try:
        resp = deepseek_chat.invoke(prompt)
        table_md = resp.content.strip()
    except Exception as e:
        msg = f"❌ 最终行程表生成失败: {e}"
        print(msg)
        return {
            "control": {
                "error_message": msg,
                "refinement_instruction": None
            }
        }

    # ========= 5️⃣ 写回状态 =========
    itinerary["final_report"] = table_md

    # 清空修改意见（否则会死循环）
    control["refinement_instruction"] = None
    control["error_message"] = None

    print("✅ 最终行程表生成完成")

    return {
        "itinerary": itinerary,
        "control": control
    }