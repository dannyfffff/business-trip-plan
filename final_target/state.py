# state.py
from typing import List, Dict, Optional, Any
from typing_extensions import TypedDict
from datetime import datetime
from data_models import CompanyInfo


# --- 定义通用数据结构 ---

class Location(TypedDict):
    """地理位置信息"""
    city: str
    address: Optional[str]
    name: Optional[str]
    lat: Optional[float]
    lon: Optional[float]


class FixedEvent(TypedDict):
    """出差期间不可移动的固定事务（会议 / 面试 / 培训等）"""
    name: str
    start_time: datetime
    end_time: datetime
    location: Location


class ItineraryItem(TypedDict):
    """行程中的一个活动或交通段"""
    type: str   # 'transport', 'company_visit', 'meeting', 'hotel'
    description: str
    start_time: datetime
    end_time: datetime
    location: Location
    details: Dict[str, Any]


class ItineraryContext(TypedDict):
    fixed_events: List[FixedEvent]

    day_1: Optional[List[ItineraryItem]]
    day_2: Optional[List[ItineraryItem]]
    day_3: Optional[List[ItineraryItem]]

    final_itinerary: List[ItineraryItem]
    final_report: str


class UserContext(TypedDict):
    """用户输入及结构化结果"""
    raw_input: str
    parsed_params: Dict[str, Any]   # 对应 UserInputParams.dict()


class LocationContext(TypedDict):
    home: Location
    hotel: Location


class TransportContext(TypedDict):
    flight_options: List[Dict]
    train_options: List[Dict]

    selected_index: Optional[int]
    selected_option_raw: Optional[Dict[str, Any]]
    selected_transport: Optional[ItineraryItem]

    approved: Optional[bool]


class CompanyContext(TypedDict):
    target_names: List[str]                          # 用户指定的公司名
    candidates: List[CompanyInfo]                    # 地理编码后的公司


class ControlContext(TypedDict):
    error_message: Optional[str]
    refinement_instruction: Optional[str]


class TravelPlanState(TypedDict):
    """
    LangGraph 全局共享状态（组合式）
    """
    user: UserContext
    locations: LocationContext
    transport: TransportContext
    companies: CompanyContext
    itinerary: ItineraryContext
    control: ControlContext

