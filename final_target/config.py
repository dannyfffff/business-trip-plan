# config.py
import os
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_qwq import ChatQwen

load_dotenv()

# 模型密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")  # qwen（仔细检查key，北京key对应国内使用，新加坡key对应国外使用）
AMAP_API_KEY = os.getenv("AMAP_API_KEY")
JUHE_TRAIN_API_KEY = os.getenv("JUHE_TRAIN_API_KEY")
SERPAPI_FLIGHTS_API_KEY = os.getenv("SERPAPI_FLIGHTS_API_KEY")


# --- 外部服务 URL ---
AMAP_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
AMAP_ROUTE_URL = "https://restapi.amap.com/v3/direction/driving"
AMAP_POI_URL = "https://restapi.amap.com/v3/place/text"
JUHE_TRAIN_QUERY_URL = "https://apis.juhe.cn/fapigw/train/query"
GOOGLE_FLIGHTS_URL = "https://serpapi.com/search.json"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


# 时间约束
PRE_MEETING_BUFFER_MINUTES = 20


# 模型类型
deepseek_chat = ChatDeepSeek(
    model="deepseek-chat",
    temperature=0.5,
)

deepseek_reasoner = ChatDeepSeek(
    model="deepseek-reasoner",
    temperature=0.5,
)

qwen_max = ChatQwen(
    model="qwen-max",
    temperature=0.5,
    timeout=30.0
)

# 城市与机场映射表
# CITY_TO_PRIMARY_IATA = {
#     "北京": "PEK",
#     "上海": "PVG",
#     "深圳": "SZX",
#     "广州": "CAN",
#     "杭州": "HGH",
#     "成都": "CTU"
# }

CITY_TO_PRIMARY_IATA = {
    "北京": ["PEK", "PKX"],
    "上海": ["PVG", "SHA"],
    "深圳": ["SZX"],
    "广州": ["CAN"],
    "杭州": ["HGH"],
    "成都": ["CTU", "TFU"],
    "重庆": ["CKG"],
    "厦门": ["XMN"],
    "福州": ["FOC"],
    "珠海": ["ZUH"],
    "南宁": ["NNG"],
    "贵阳": ["KWE"],
    "兰州": ["LHW"],
    "拉萨": ["LXA"],
    "西安": ["XIY"],
    "天津": ["TSN"],
    "合肥": ["HFE"],
    "济南": ["TNA"],
    "石家庄": ["SJW"],
    "郑州": ["CGO"],
    "武汉": ["WUH"],
    "长沙": ["CSX"],
    "太原": ["TYN"],
    "大连": ["DLC"],
    "青岛": ["TAO"],
    "宁波": ["NGB"],
    "哈尔滨": ["HRB"],
    "沈阳": ["SHE"],
    "长春": ["CGQ"],
    "乌鲁木齐": ["URC"],
    "呼和浩特": ["HET"],
    "银川": ["INC"],
    "三亚": ["SYX"],
    "海口": ["HAK"],
    "台北": ["TSA", "TPE"],
    "高雄": ["KHH"],
    "澳门": ["MFM"],
    "香港": ["HKG"],
    "遵义": ["ZYI"],
    "十堰": ["WDS"],
    "衡阳": ["HNY"],
    "东莞": ["DGM"],
    "温州": ["WNZ"],
    "泉州": ["JJN"],
    "惠州": ["HUZ"],
    "佛山": ["FUO"],
    "揭阳": ["SWA"],
    "湛江": ["ZHA"],
    "汕头": ["SWA"],
    "潮州": ["SWA"],
    "北海": ["BHY"],
    "桂林": ["KWL"],
    "柳州": ["LZH"],
    "百色": ["AEB"],
    "梧州": ["WUZ"]
}

AIRPORT_CODE_TO_NAME = {
    "PEK": "北京首都机场",
    "PKX": "北京大兴机场",
    "PVG": "上海浦东机场",
    "SHA": "上海虹桥机场",
    "SZX": "深圳宝安机场",
    "CAN": "广州白云机场",
    "HGH": "杭州萧山机场",
    "CTU": "成都双流机场",
    "TFU": "成都天府机场",
    "XMN": "厦门高崎机场",
    "FOC": "福州长乐机场",
    "ZUH": "珠海金湾机场",
    "NNG": "南宁吴圩机场",
    "KWE": "贵阳龙洞堡机场",
    "LHW": "兰州中川机场",
    "LXA": "拉萨贡嘎机场",
    "XIY": "西安咸阳机场",
    "TSN": "天津滨海机场",
    "HFE": "合肥新桥机场",
    "TNA": "济南遥墙机场",
    "SJW": "石家庄正定机场",
    "CGO": "郑州新郑机场",
    "WUH": "武汉天河机场",
    "CSX": "长沙黄花机场",
    "TYN": "太原武宿机场",
    "DLC": "大连周水子机场",
    "TAO": "青岛胶东机场",
    "NGB": "宁波栎社机场",
    "HRB": "哈尔滨太平机场",
    "SHE": "沈阳桃仙机场",
    "CGQ": "长春龙嘉机场",
    "URC": "乌鲁木齐地窝堡机场",
    "HET": "呼和浩特白塔机场",
    "INC": "银川河东机场",
    "SYX": "三亚凤凰机场",
    "HAK": "海口美兰机场",
    "TSA": "台北松山机场",
    "TPE": "台北桃园机场",
    "KHH": "高雄国际机场",
    "MFM": "澳门国际机场",
    "HKG": "香港国际机场",
    "ZYI": "遵义新舟机场",
    "WDS": "十堰武当山机场",
    "HNY": "衡阳南岳机场",
    "DGM": "东莞虚拟运输机场",
    "WNZ": "温州龙湾机场",
    "JJN": "泉州晋江机场",
    "HUZ": "惠州机场",
    "FUO": "佛山沙堤机场",
    "SWA": "潮汕国际机场",
    "ZHA": "湛江机场",
    "BHY": "北海福成机场",
    "KWL": "桂林两江国际机场",
    "LZH": "柳州白莲机场",
    "AEB": "百色巴马机场",
    "WUZ": "梧州长洲岛机场"
}


