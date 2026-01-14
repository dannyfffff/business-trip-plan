from datetime import datetime
from typing import Union

from llm_agent import parse_user_input
from nodes.geo_process import geocode_locations
from nodes.input_check import check_constraints
from state import TravelPlanState

# 模拟用户输入文本
test_input = """
我要从上海出发去深圳，出发日期是 2026-01-15。
我有两个事件： 
1. 企业拜访：深圳市南山区深南大道10000号，时间 2026-01-15 14:00，持续 2 小时。
2. 调研会议：深圳市南山区桃园路2号，时间 2026-01-17 15:00，持续 1.5 小时。
我的住址：上海市浦东新区川沙新镇黄赵路310号。
酒店地址：深圳市南山区西丽街道官龙村西82号。
"""

# 调用函数
result: Union[dict, dict] = parse_user_input(test_input)

# 输出结果
if "error_message" in result:
    print("解析失败:", result["error_message"])
else:
    print("解析成功，结构化输出:")
    from pprint import pprint
    pprint(result)


initial_state = TravelPlanState(
    user={
        "raw_input": test_input,
        "parsed_params": {}
    }
)
pprint(check_constraints(initial_state))
pprint(geocode_locations(initial_state))

