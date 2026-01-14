#route_plan.py
from llm_agent import llm_choose_transport
from state import TravelPlanState
from typing import Dict, Any, List
import time
from tools.travel_api import query_flight_api, query_train_api, amap_geocode, get_amap_driving_time
import requests
from state import Location
from langgraph.types import interrupt

def traffic_query(state: TravelPlanState) -> Dict[str, Any]:
    """
    节点 3：交通查询
    """
    print("\n--- 🚅 节点 3: 交通查询开始 ---")

    parsed = state["user"]["parsed_params"]
    origin = parsed["origin_city"]
    destination = parsed["destination_city"]
    departure_date = parsed["departure_date"]

    flight_options: List[Dict] = []
    train_options: List[Dict] = []

    print(f"   查询区间: {origin} -> {destination} | 日期: {departure_date}")

    # ========= 航班查询（带重试） =========
    max_retry = 3
    for attempt in range(1, max_retry + 1):
        try:
            flight_options = query_flight_api(
                origin=origin,
                destination=destination,
                date=departure_date
            )
            break
        except (requests.exceptions.SSLError,
                requests.exceptions.ConnectionError) as e:
            print(f"⚠️ 航班查询失败，第 {attempt} 次重试: {e}")
            time.sleep(3)

    # ========= 高铁查询 =========
    try:
        train_options = query_train_api(
            origin=origin,
            destination=destination,
            date=departure_date
        )
    except Exception as e:
        print(f"⚠️ 高铁查询异常，已忽略: {e}")
        train_options = []

    total = len(flight_options) + len(train_options)

    if total == 0:
        return {
            "control": {
                "error_message": f"未查询到 {origin} 到 {destination} 的任何交通选项。"
            }
        }

    print(f"✅ 交通查询完成：航班 {len(flight_options)} 个，高铁 {len(train_options)} 个")

    return {
        "transport": {
            "flight_options": flight_options,
            "train_options": train_options
        },
        "control": {
            "error_message": None
        }
    }


def select_transport_by_llm(state: TravelPlanState) -> Dict[str, Any]:
    """
    节点 4: 交通方式与班次选择
    """
    original_transport_ctx = state["transport"]
    user_params = state["user"]["parsed_params"]

    fixed_events = user_params.get("fixed_events", [])
    if not fixed_events:
        return {"control": {"error_message": "未提供任何固定事务，无法进行交通决策"}}

    # 选取「最早开始的固定事务」作为交通约束锚点
    earliest_event = min(
        fixed_events,
        key=lambda e: e["start_time"]
    )
    event_loc = earliest_event["location"]

    flight_options = state["transport"].get("flight_options", [])
    train_options = state["transport"].get("train_options", [])
    transport_options = flight_options + train_options

    if not transport_options:
        return {"control": {"error_message": "无可用交通方案"}}

    print("\n--- 🧠 节点 4: LLM 交通决策开始 ---")

    # 选一个参考班次，仅用于估算「到达枢纽 → 固定事务地点」通勤
    ref_option = transport_options[0]

    ref_arrival_hub = ref_option["arrival_hub"]
    ref_arr_coords = amap_geocode(ref_arrival_hub, event_loc["city"])
    if not ref_arr_coords:
        return {
            "control": {
                "error_message": f"到达枢纽 {ref_arrival_hub} 无法地理编码"
            }
        }

    arrival_hub_loc: Location = {
        "city": event_loc["city"],
        "address": ref_arrival_hub,
        "name": ref_arrival_hub,
        "lat": ref_arr_coords["lat"],
        "lon": ref_arr_coords["lon"],
    }

    # ✅ 仅计算：到达枢纽 → 最早固定事务地点
    arrival_commute_minutes = (
        get_amap_driving_time(arrival_hub_loc, event_loc) or 60.0
    )

    print(
        f"   -> 枢纽到最早固定事务地点参考通勤时间："
        f"{arrival_commute_minutes:.1f} 分钟"
    )

    selected_option = llm_choose_transport(
        transport_options=transport_options,
        user_params=user_params,
        arrival_commute_minutes=arrival_commute_minutes,
        anchor_event_start=earliest_event["start_time"]
    )

    if not selected_option:
        return {
            "control": {
                "error_message": "LLM 未能选出有效交通方案"
            }
        }

    print(f"✅ 选定班次: {selected_option['type']} {selected_option['id']}")

    return {
        "transport": {
            **original_transport_ctx,
            "selected_option_raw": selected_option
        },
        "control": {
            "error_message": None
        }
    }


def user_select_transport(state: TravelPlanState) -> Dict[str, Any]:
    """
    节点 4.x：用户手动选择交通方案

    行为：
    1. 汇总所有可选交通方案
    2. 通过 interrupt 明确展示方案列表
    3. 接收用户选择索引
    4. 将选中方案写入 transport.selected_option_raw
    """
    print("\n--- 👤 用户手动选择交通方案节点 ---")

    transport_ctx = state.get("transport", {})
    flight_options = transport_ctx.get("flight_options", [])
    train_options = transport_ctx.get("train_options", [])

    all_options = flight_options + train_options

    selectable_options = [
        opt for opt in all_options
        if isinstance(opt.get("price"), (int, float))
    ]

    if not selectable_options:
        return {
            "control": {
                "error_message": "当前没有可供用户选择的交通方案"
            }
        }

    # 按出发时间排序，便于人工决策
    selectable_options.sort(key=lambda x: x.get("departure_time", ""))

    print(f"   -> 可选方案数量: {len(selectable_options)}")

    # 2️⃣ 构造可直接展示给用户的文本列表
    option_summaries = []
    for idx, opt in enumerate(selectable_options):
        option_summaries.append(
            f"[{idx}] {opt.get('type')} {opt.get('id')} | "
            f"{opt.get('departure_time')} → {opt.get('arrival_time')} | "
            f"{opt.get('departure_hub_name')} → {opt.get('arrival_hub_name')} "
        )

    # 3️⃣ 触发中断：明确把“方案列表”传出去
    user_response = interrupt({
        "type": "select_transport",
        "message": "请选择一个交通方案，可输入该方案对应的数字：",
        "options": option_summaries
    })

    print(f"DEBUG: 用户返回的数据: {user_response}")

    # 4️⃣ 解析用户选择
    selected_index = int(user_response)

    if not isinstance(selected_index, int):
        return {
            "control": {
                "error_message": f"用户返回值不是索引整数: {user_response}"
            }
        }

    if not (0 <= selected_index < len(selectable_options)):
        return {
            "control": {
                "error_message": f"用户选择索引越界: {selected_index}"
            }
        }

    selected_option = selectable_options[selected_index]

    print(
        f"✅ 用户选择方案: "
        f"{selected_option.get('type')} {selected_option.get('id')}"
    )

    # 5️⃣ 写回状态（结构与 LLM 选中保持一致）
    return {
        "transport": {
            **transport_ctx,
            "selected_option_raw": selected_option
        },
        "control": {
            "error_message": None
        }
    }
