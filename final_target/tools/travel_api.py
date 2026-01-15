#travel_api.py
from typing import Dict, List, Optional, Any, Union
import requests
import time
from config import AMAP_API_KEY, AMAP_GEOCODE_URL, CITY_TO_PRIMARY_IATA, SERPAPI_FLIGHTS_API_KEY, GOOGLE_FLIGHTS_URL, \
    JUHE_TRAIN_API_KEY, JUHE_TRAIN_QUERY_URL, AMAP_ROUTE_URL, AIRPORT_CODE_TO_NAME
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_models import CompanyInfo
from state import Location, ItineraryItem

MAX_RETRIES = 5 # 最大重试次数
INITIAL_WAIT_TIME = 1.0 # 初始等待时间（秒）

def amap_geocode(address: str, city: str) -> Optional[Dict[str, float]]:
    """
    调用高德地理编码 API，返回 {"lat": float, "lon": float}
    失败返回 None（允许流程继续）
    """
    if not AMAP_API_KEY:
        print("❌ 致命错误：AMAP_API_KEY 未配置，无法进行地理编码。")
        return None

    params = {
        "key": AMAP_API_KEY,
        "address": address,
        "city": city,
        "output": "json"
    }

    wait_time = INITIAL_WAIT_TIME

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                AMAP_GEOCODE_URL,
                params=params,
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            # 1️⃣ 高德 API 成功
            if data.get("status") == "1" and int(data.get("count", 0)) > 0:
                location_str = data["geocodes"][0].get("location")

                if location_str:
                    lon, lat = map(float, location_str.split(","))
                    return {"lat": lat, "lon": lon}

                print("⚠️ 高德返回成功，但 location 字段为空。")
                return None

            # 2️⃣ 高德 API 返回失败（如配额、参数错误）
            print(
                f"⚠️ 高德地理编码失败（第 {attempt} 次） | "
                f"status={data.get('status')} info={data.get('info')}"
            )

        except requests.exceptions.RequestException as e:
            print(f"❌ 高德 API 请求异常（第 {attempt} 次）: {e}")

        except Exception as e:
            print(f"❌ 解析高德返回数据异常（第 {attempt} 次）: {e}")
            return None  # 结构异常没必要重试

        # 3️⃣ 未成功则等待后重试
        if attempt < MAX_RETRIES:
            time.sleep(wait_time)
            wait_time *= 2  # 指数退避

    print(f"❌ 地理编码最终失败（已重试 {MAX_RETRIES} 次）: {address} | {city}")
    return None


THROTTLE_DELAY = 0.34  # 强制冷却时间，用于控制 QPS
def get_amap_driving_time(origin: Union[Location, Dict[str, Any]], destination: Union[Location, Dict[str, Any]]) -> Optional[float]:
    """
    实际调用高德路径规划API，计算两个地点间的驾车耗时（分钟）。
    加入延时、指数退避重试机制和强制冷却，以解决 QPS 超限问题。

    Args:
        origin: 起点 Location 结构 (需要 lat/lon)。
        destination: 终点 Location 结构 (需要 lat/lon)。

    Returns:
        驾车耗时（分钟），失败返回 None。
    """
    if not AMAP_API_KEY:
        print("❌ 致命错误：AMAP_API_KEY 未配置，无法计算驾车时间。")
        return None

    # 1. 检查经纬度是否可用
    # 假设 Location 是一个字典，键是 'lat' 和 'lon'
    if not origin.get('lat') or not destination.get('lat'):
        print(f"⚠️ 无法计算驾车时间: 起点或终点的经纬度缺失。")
        return 35.0

    # 2. 构造请求参数
    origin_coords = f"{origin['lon']},{origin['lat']}"
    destination_coords = f"{destination['lon']},{destination['lat']}"

    params = {
        "key": AMAP_API_KEY,
        "origin": origin_coords,
        "destination": destination_coords,
        "output": "json",
        "extensions": "base",
        "strategy": 0
    }

    wait_time = INITIAL_WAIT_TIME

    # === 循环重试机制开始 ===
    for attempt in range(MAX_RETRIES):
        try:
            # 1. 发送请求
            response = requests.get(AMAP_ROUTE_URL, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()

            # 2. 检查高德 API 状态码
            if data.get("status") == "1" and int(data.get("count", 0)) > 0:
                # 路径规划成功，返回结果
                route = data['route']['paths'][0]
                duration_seconds = int(route.get('duration', 0))

                # 🚨 修正点 1：成功后强制等待，防止连续调用超限
                time.sleep(THROTTLE_DELAY)

                return round(duration_seconds / 60.0, 1)

            # 3. API 错误处理，特别是针对 QPS 超限
            error_reason = data.get('info', '未知错误')

            # 检查是否为 QPS 或配额相关错误
            is_limit_error = (data.get("status") == "0" and
                              ('LIMIT' in error_reason.upper() or
                               'QUOTA' in error_reason.upper()))

            if is_limit_error:
                if attempt < MAX_RETRIES - 1:
                    # 进行重试：失败时等待更久（指数退避）
                    print(f"🚦 QPS 超限，尝试第 {attempt + 1} 次重试，等待 {wait_time:.1f} 秒...")
                    time.sleep(wait_time)
                    wait_time *= 2
                    continue
                else:
                    # 达到最大重试次数
                    print(f"❌ 高德路径规划失败: 已达最大重试次数，原因: {error_reason}")
                    return None
            else:
                # 其他 API 错误（例如参数错误等），不重试
                print(f"⚠️ 高德路径规划 API 返回失败。状态码: {data.get('status')}, 原因: {error_reason}")
                return None

        except requests.exceptions.RequestException as e:
            # 网络或 HTTP 错误
            if attempt < MAX_RETRIES - 1:
                print(f"❌ API 请求失败 (网络错误)，尝试第 {attempt + 1} 次重试，等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time)
                wait_time *= 2
                continue
            else:
                print(f"❌ 高德路径规划 API 请求失败: {e}")
                return None

        except Exception as e:
            # 捕获其他未知错误 (如 JSON 解析错误)
            print(f"❌ 处理高德路径规划 API 响应时发生错误: {e}")
            return None

    return None


def get_iata_code(city_name: str) -> Optional[str]:
    """根据城市名获取其主要 IATA 代码。"""
    if not city_name:
        return None
    return CITY_TO_PRIMARY_IATA.get(city_name.strip(), None)


# def query_flight_api(origin: str, destination: str, date: str) -> List[Dict]:
#     """
#     使用 SerpApi 的 google_flights 引擎查询航班，输入使用 IATA 代码。
#     返回统一结构的航班列表。
#     """
#     print(f"✈️ 正在查询 {origin} -> {destination} 航班，日期: {date}")
#
#     departure_iata = get_iata_code(origin)
#     arrival_iata = get_iata_code(destination)
#
#     if not departure_iata or not arrival_iata:
#         print(f"⚠️ 无法获取 IATA 代码：{origin} / {destination}")
#         return []
#
#     params = {
#         "engine": "google_flights",
#         "departure_id": departure_iata,
#         "arrival_id": arrival_iata,
#         "outbound_date": date,
#         "currency": "CNY",
#         "hl": "zh-cn",
#         "api_key": SERPAPI_FLIGHTS_API_KEY,
#         "type": "2",
#         "stops": "0"
#     }
#
#     try:
#         time.sleep(1)
#         response = requests.get(GOOGLE_FLIGHTS_URL, params=params, timeout=20)
#         response.raise_for_status()
#         data = response.json()
#
#         flight_groups = data.get("best_flights", []) + data.get("other_flights", [])
#         flights: List[Dict] = []
#
#         for group in flight_groups:
#             segments = group.get("flights", [])
#             if len(segments) != 1 or "price" not in group:
#                 continue
#
#             seg = segments[0]
#             dep_time = seg.get("departure_airport", {}).get("time")
#             arr_time = seg.get("arrival_airport", {}).get("time")
#
#             if not dep_time or not arr_time:
#                 continue
#
#             try:
#                 dep_dt = datetime.strptime(dep_time, "%Y-%m-%d %H:%M")
#                 arr_dt = datetime.strptime(arr_time, "%Y-%m-%d %H:%M")
#             except ValueError:
#                 continue
#
#             flights.append({
#                 "type": "Flight",
#                 "id": seg.get("flight_number", "N/A"),
#
#                 "departure_date": dep_dt.strftime("%Y-%m-%d"),
#                 "departure_time": dep_dt.strftime("%H:%M"),
#                 "arrival_date": arr_dt.strftime("%Y-%m-%d"),
#                 "arrival_time": arr_dt.strftime("%H:%M"),
#
#                 "departure_hub": seg.get("departure_airport", {}).get("id"),
#                 "arrival_hub": seg.get("arrival_airport", {}).get("id"),
#
#                 "duration": group.get("total_duration"),
#                 "price": group.get("price"),
#             })
#
#         print(f"✅ 航班查询完成，共 {len(flights)} 个结果")
#         return flights
#
#     except requests.exceptions.RequestException as e:
#         print(f"❌ SerpApi 航班查询失败: {e}")
#         return []
#     except Exception as e:
#         print(f"❌ 航班数据解析异常: {e}")
#         return []

def get_airport_name(code: str) -> str:
    """获取机场中文名，如果找不到则返回原代码"""
    return AIRPORT_CODE_TO_NAME.get(code.upper(), code)

def query_flight_api(origin: str, destination: str, date: str) -> List[Dict]:
    """
    支持多机场城市的航班查询。
    内部自动将 2026-1-15 转换为 2026-01-15 以适配 SerpApi 要求。
    """
    # --- 🚨 核心修复：日期强制格式化 ---
    try:
        # 即使输入是 2026-1-15，也会被统一转为 2026-01-15
        dt_obj = datetime.strptime(date.replace("/", "-"), "%Y-%m-%d")
        standard_date = dt_obj.strftime("%Y-%m-%d")
    except Exception as e:
        print(f"❌ 日期解析失败: {date}, 请确保格式为 YYYY-MM-DD")
        return []

    print(f"✈️ 正在查询 {origin} -> {destination} 航班，标准日期: {standard_date}")

    # --- 🚨 核心修复：多机场映射逻辑 ---
    # 如果城市名在映射表里，取列表；否则把城市名转成列表处理
    dep_iatas = CITY_TO_PRIMARY_IATA.get(origin.strip(), [origin.strip()])
    arr_iatas = CITY_TO_PRIMARY_IATA.get(destination.strip(), [destination.strip()])

    # 内部执行单次请求的闭包函数（保持你原有的逻辑）
    def fetch_single(d_iata, a_iata):
        params = {
            "engine": "google_flights",
            "departure_id": d_iata,
            "arrival_id": a_iata,
            "outbound_date": standard_date,  # 使用标准日期
            "currency": "CNY",
            "hl": "zh-cn",
            "api_key": SERPAPI_FLIGHTS_API_KEY,
            "type": "2",
            "stops": "0"
        }
        try:
            # 这里的逻辑完全保留你原来的解析流程
            response = requests.get(GOOGLE_FLIGHTS_URL, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            flight_groups = data.get("best_flights", []) + data.get("other_flights", [])
            local_flights = []

            for group in flight_groups:
                segments = group.get("flights", [])
                if len(segments) != 1 or "price" not in group:
                    continue
                seg = segments[0]
                dep_time = seg.get("departure_airport", {}).get("time")
                arr_time = seg.get("arrival_airport", {}).get("time")
                if not dep_time or not arr_time: continue

                try:
                    dep_dt = datetime.strptime(dep_time, "%Y-%m-%d %H:%M")
                    arr_dt = datetime.strptime(arr_time, "%Y-%m-%d %H:%M")
                except ValueError:
                    continue

                local_flights.append({
                    "type": "Flight",
                    "id": seg.get("flight_number", "N/A"),
                    "departure_date": dep_dt.strftime("%Y-%m-%d"),
                    "departure_time": dep_dt.strftime("%H:%M"),
                    "arrival_date": arr_dt.strftime("%Y-%m-%d"),
                    "arrival_time": arr_dt.strftime("%H:%M"),
                    "departure_hub": seg.get("departure_airport", {}).get("id"),
                    "arrival_hub": seg.get("arrival_airport", {}).get("id"),
                    "departure_hub_name": get_airport_name(seg.get("departure_airport", {}).get("id")),
                    "arrival_hub_name": get_airport_name(seg.get("arrival_airport", {}).get("id")),
                    "duration": group.get("total_duration"),
                    "price": group.get("price"),
                })
            return local_flights
        except Exception as e:
            print(f"❌ {d_iata}->{a_iata} 局部请求失败: {e}")
            return []

    # --- 🚨 核心修复：并发执行 ---
    all_combined_flights = []
    # 组合所有机场对
    tasks = [(d, a) for d in dep_iatas for a in arr_iatas]

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single, d, a): (d, a) for d, a in tasks}
        for future in as_completed(futures):
            res = future.result()
            if res:
                all_combined_flights.extend(res)

    # 去重并按起飞时间排序
    unique_flights = []
    seen = set()
    for f in all_combined_flights:
        key = f"{f['id']}_{f['departure_time']}"
        if key not in seen:
            unique_flights.append(f)
            seen.add(key)

    unique_flights.sort(key=lambda x: x['departure_time'])

    print(f"✅ 航班查询完成，多机场汇总后共 {len(unique_flights)} 个结果")
    return unique_flights




def query_train_api(origin: str, destination: str, date: str, filter: str = "G") -> List[Dict]:
    """
    调用聚合数据 API 查询高铁，返回统一结构的车次列表。
    """
    print(f"🚄 查询高铁 {origin} -> {destination} | 日期: {date}")

    if not JUHE_TRAIN_API_KEY:
        print("⚠️ JUHE_TRAIN_API_KEY 未配置，使用模拟数据")
        return [{
            "type": "Train",
            "id": "G101",
            "departure_date": date,
            "departure_time": "07:30",
            "arrival_date": date,
            "arrival_time": "13:30",
            "price": 600,
            "duration": "6h00m",
            "departure_hub": f"{origin}站",
            "arrival_hub": f"{destination}站",
        }]

    params = {
        "key": JUHE_TRAIN_API_KEY,
        "search_type": "1",
        "departure_station": origin,
        "arrival_station": destination,
        "date": date,
        "enable_booking": "1",
        "filter": filter
    }

    try:
        response = requests.get(JUHE_TRAIN_QUERY_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("error_code") != 0:
            print(f"⚠️ 高铁查询失败: {data.get('reason')}")
            return []

        trains: List[Dict] = []

        for item in data.get("result", []):
            dep_time = item["departure_time"]
            arr_time = item["arrival_time"]

            dep_dt = datetime.strptime(f"{date} {dep_time}", "%Y-%m-%d %H:%M")
            arr_dt = datetime.strptime(f"{date} {arr_time}", "%Y-%m-%d %H:%M")

            if arr_dt < dep_dt:
                arr_dt += timedelta(days=1)

            price_item = next(
                (p for p in item.get("prices", []) if p.get("seat_name") == "二等座"),
                {"price": 0}
            )

            trains.append({
                "type": "Train",
                "id": item["train_no"],

                "departure_date": dep_dt.strftime("%Y-%m-%d"),
                "departure_time": dep_dt.strftime("%H:%M"),
                "arrival_date": arr_dt.strftime("%Y-%m-%d"),
                "arrival_time": arr_dt.strftime("%H:%M"),

                "departure_hub": item["departure_station"],
                "arrival_hub": item["arrival_station"],
                "departure_hub_name": item["departure_station"],
                "arrival_hub_name": item["arrival_station"],
                "duration": item["duration"],
                "price": price_item["price"],
            })

        print(f"✅ 高铁查询完成，共 {len(trains)} 个结果")
        return trains

    except requests.exceptions.RequestException as e:
        print(f"❌ 聚合数据 API 请求失败: {e}")
        return []
    except Exception as e:
        print(f"❌ 高铁数据解析异常: {e}")
        return []


def generate_day1_commute_matrix(
    transport_item: ItineraryItem,
    day1_events: List[Any],
    hotel_loc: Location
) -> Dict[str, Dict[str, float]]:
    """
    生成 Day 1 的通勤矩阵：
    - 包含到达交通站、酒店、以及 Day 1 固定事务
    - 返回矩阵，键为 LOC_i，值为各点到其他点的驾车分钟数
    """

    locations = []
    # 1️⃣ 到达交通站
    arrival_loc = transport_item["location"]
    locations.append(arrival_loc)
    # 2️⃣ 酒店
    locations.append(hotel_loc)
    # 3️⃣ Day 1 固定事务
    for event in day1_events:
        locations.append(event["location"])

    # ========= 生成通勤矩阵 =========
    matrix = {}
    for i in range(len(locations)):
        matrix[f"LOC_{i}"] = {}
        for j in range(len(locations)):
            # 调用高德 API 获取驾车时间
            time_minutes = get_amap_driving_time(locations[i], locations[j])
            matrix[f"LOC_{i}"][f"LOC_{j}"] = time_minutes if time_minutes is not None else 60.0

    return matrix


def generate_day23_commute_matrix(
    day2_events: List[Any],
    day3_events: List[Any],
    companies_to_plan: List[CompanyInfo],
    hotel_loc: Location
) -> Dict[str, Dict[str, float]]:
    """
    生成 Day 2/3 的通勤矩阵：
    - 包含 Day 2/3 的固定事件、待调研企业、酒店
    - 返回矩阵，键为 LOC_i，值为各点到其他点的驾车分钟数
    """

    locations: List[Location] = []

    # 1️⃣ 酒店
    locations.append(hotel_loc)

    # 2️⃣ Day 2 固定事件
    for event in day2_events:
        locations.append(event["location"])

    # 3️⃣ Day 3 固定事件
    for event in day3_events:
        locations.append(event["location"])

    # 4️⃣ 待调研企业
    for company in companies_to_plan:
        # ⚠️ 关键修正：从 CompanyInfo 对象的字段构造 Location TypedDict
        company_location: Location = {
            "city": hotel_loc["city"],
            "address": company.address,
            "name": company.name,
            "lat": company.lat,
            "lon": company.lon
        }
        locations.append(company_location)

    # ========= 生成通勤矩阵 =========
    matrix: Dict[str, Dict[str, float]] = {}
    for i in range(len(locations)):
        matrix[f"LOC_{i}"] = {}
        for j in range(len(locations)):
            if i == j:
                matrix[f"LOC_{i}"][f"LOC_{j}"] = 0.0
            else:
                time_minutes = get_amap_driving_time(locations[i], locations[j])
                matrix[f"LOC_{i}"][f"LOC_{j}"] = time_minutes if time_minutes is not None else 60.0

    return matrix
