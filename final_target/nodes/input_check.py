#input_check.py
from llm_agent import parse_user_input
from state import TravelPlanState
from datetime import datetime
from typing import Dict, Any


def check_constraints(state: TravelPlanState) -> Dict[str, Any]:
    """
    节点 1：信息与约束校验。
    - 校验输入完整性
    - 校验时间格式
    - 初始化 Location / FixedEvent
    """
    user_input = state["user"]["raw_input"]
    user_data = parse_user_input(user_input)

    # 0. LLM 解析失败直接返回
    if "error_message" in user_data:
        return {
            "control": {
                "error_message": user_data["error_message"]
            }}

    # 1. 必要字段校验
    required_keys = [
        "origin_city",
        "destination_city",
        "departure_date",
        "home_address",
        "hotel_address",
        "fixed_events",
    ]
    missing = [k for k in required_keys if not user_data.get(k)]

    if missing:
        return {
            "control": {
                "error_message": f"缺少关键输入信息: {', '.join(missing)}"
            }
        }

    try:
        # 3. 校验并标准化 fixed_events 时间
        fixed_events = []
        for event in user_data["fixed_events"]:
            start = event["start_time"]
            end = event["end_time"]

            # 允许字符串输入，统一转为 datetime
            if isinstance(start, str):
                start = datetime.strptime(start, "%Y-%m-%d %H:%M")
            if isinstance(end, str):
                end = datetime.strptime(end, "%Y-%m-%d %H:%M")

            if end <= start:
                raise ValueError("事件结束时间必须晚于开始时间")

            fixed_events.append({
                **event,    #解包操作，将 name、location 等键值对完整地复制到新字典中。
                "start_time": start,
                "end_time": end,
            })

        # 4. 初始化 Location
        locations = {
            "home": {
                "city": user_data["origin_city"],
                "address": user_data["home_address"],
                "name": "Home",
                "lat": None,
                "lon": None,
            },
            "hotel": {
                "city": user_data["destination_city"],
                "address": user_data["hotel_address"],
                "name": "Hotel",
                "lat": None,
                "lon": None,
            },
        }

        return {
            "user": {
                "raw_input": user_input,
                "parsed_params": {
                    # 因为"parsed_params"是浅层，必须要有解包操作，否则"parsed_params"会被更新为只含"fixed_events"，
                    # 而其他不需要更新的顶层键，例如transport,company会被自动保留。
                    **user_data,
                    "fixed_events": fixed_events,
                }
            },
            "locations": locations,
            "control": {
                "error_message": None
            }
        }

    except ValueError as e:
        return {
            "control": {
                "error_message": f"时间格式或逻辑错误: {e}"
            }
        }
    except Exception as e:
        return {
            "control": {
                "error_message": f"约束校验阶段发生异常: {e}"
            }
        }
