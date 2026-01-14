#geo_process.py
from typing import Dict, Any, List
from data_models import CompanyInfo
from llm_agent import geocode_company_by_name
from state import TravelPlanState
from tools.travel_api import amap_geocode


def geocode_locations(state: TravelPlanState) -> Dict[str, Any]:
    """
    节点 2：地理编码
    - 对 home / hotel / fixed_events.location 进行批量地理编码
    - 写回 lat / lon
    """
    print("\n--- 📍 节点 2: 地理编码开始 ---")

    locations = state["locations"]
    original_user_ctx = state["user"]
    original_parsed_params = state["user"]["parsed_params"]
    fixed_events = original_parsed_params["fixed_events"]

    # 1. 需要编码的 Location 汇总
    locations_to_geocode = {
        "home": locations.get("home"),
        "hotel": locations.get("hotel"),
    }

    # 2. 编码 home / hotel
    for key, loc in locations_to_geocode.items():
        if not loc or not loc.get("address"):
            continue

        coords = amap_geocode(loc["address"], loc["city"])
        if coords:
            loc["lat"] = coords["lat"]
            loc["lon"] = coords["lon"]
            print(f"   ✔ {loc['name']} -> ({loc['lat']}, {loc['lon']})")
        else:
            print(f"   ⚠ 编码失败: {loc['name']}")

    # 3. 编码 fixed_events 的 location
    for idx, event in enumerate(fixed_events, start=1):
        loc = event.get("location")
        if not loc or not loc.get("address"):
            continue

        coords = amap_geocode(loc["address"], loc["city"])
        if coords:
            loc["lat"] = coords["lat"]
            loc["lon"] = coords["lon"]
            print(f"   ✔ Event {idx}: {event['name']} -> ({loc['lat']}, {loc['lon']})")
        else:
            print(f"   ⚠ Event {idx} 编码失败: {event['name']}")

    return {
        "locations": locations,
        "user": {
            **original_user_ctx,
            "parsed_params": {
                **original_parsed_params,
                "fixed_events": fixed_events
            }
        },
        "control": {
            "error_message": None
        }
    }


def geocode_companies(state: TravelPlanState) -> Dict[str, Any]:
    """
    geocode_companies：
    - 读取 companies.target_names
    - 调用地理编码函数
    - 生成 CompanyInfo 列表
    - 写回 companies.candidates
    """

    print("\n--- 📍 节点: geocode_companies ---")

    target_names = state["companies"].get("target_names", [])

    if not target_names:
        return {
            "control": {
                "error_message": "未提供需要地理编码的企业名称"
            }
        }

    geocoded_companies: List[CompanyInfo] = []

    for name in target_names:
        geo = geocode_company_by_name(
            company_name=name,
            city=state["locations"]["hotel"]["city"]
        )

        if geo is None:
            company_info = CompanyInfo(
                name=name,
                address="none",
                lat=None,
                lon=None,
                is_valid=False
            )
        else:
            company_info = CompanyInfo(
                name=name,
                address=geo["address"],
                lat=geo["lat"],
                lon=geo["lon"],
                is_valid=True
            )

        geocoded_companies.append(company_info)

        print(
            f"🏢 {name} | "
            f"{company_info.address} | "
            f"({company_info.lat}, {company_info.lon}) | "
            f"valid={company_info.is_valid}"
        )

    # 写回 CompanyContext
    return {
        "companies": {
            **state["companies"],
            "candidates": geocoded_companies
        },
        "control": {
            "error_message": None
        }
    }

