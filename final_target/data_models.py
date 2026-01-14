#data_models.py
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class SelectedTransport(BaseModel):
    type: str = Field(description="选定的交通工具类型，如 'Flight' 或 'Train'。")
    id: str = Field(description="选定班次的唯一标识符/编号。")
    reasoning: str = Field(description="选择该班次的推理理由，需要解释如何满足调研时间最大化。")

class FixedEventLocation(BaseModel):
    city: str
    address: str
    name: str
    lat: Optional[float] = None
    lon: Optional[float] = None

class FixedEvent(BaseModel):
    name: str = Field(description="事务名称，如会议、培训或拜访企业等。")
    start_time: datetime = Field(description="事务开始时间。")
    end_time: datetime = Field(description="事务结束时间。")
    location: FixedEventLocation = Field(description="事务地点信息。")

class UserInputParams(BaseModel):
    """用户输入中必须提取的全部关键参数。"""
    origin_city: str = Field(description="出发城市名，例如 '上海'。")
    destination_city: str = Field(description="目的地城市名，例如 '深圳'。")
    departure_date: str = Field(description="出发日期，格式为 'YYYY-MM-DD'。")
    home_address: str = Field(description="用户的出发地详细地址。")
    hotel_address: str = Field(description="预订或计划入住的酒店详细地址。")
    fixed_events: List[FixedEvent] = Field(
        description="用户出差过程中必须安排的固定事务列表（会议、培训、拜访等）。"
    )

class CompanyInfo(BaseModel):
    name: str
    address: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    is_valid: bool = True


class CompanyGroup(BaseModel):
    """一组相关的公司推荐。"""
    companies: List[str] = Field(description="包含三家公司的名称列表。")

class CompanyRecommendations(BaseModel):
    """LLM 推荐的三组公司，每组包含三家公司。"""
    recommendation_groups: List[CompanyGroup] = Field(
        description="包含三个推荐组的列表。每个组应包含三家公司。"
    )