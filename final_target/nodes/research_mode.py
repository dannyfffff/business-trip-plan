#research_mode.py
from typing import Dict, Any, List
from langgraph.types import interrupt
from llm_agent import generate_company_recommendations_by_llm
from state import TravelPlanState


def custom_research(state: TravelPlanState) -> Dict[str, Any]:

    print("\n--- 🧭 节点: custom_research ---")

    companies = state.get("companies")
    if not companies:
        return {
            "control": {
                "error_message": "companies 上下文不存在"
            }
        }

    target_names = companies.get("target_names")

    if not target_names:
        return {
            "control": {
                "error_message": "未提供自定义调研企业名称"
            }
        }

    print(f"✅ 使用用户自定义调研企业：{target_names}")

    return {
        "companies": {
            "target_names": target_names,
            "candidates": []
        },
        "control": {
            "error_message": None
        }
    }


# def auto_research(state: TravelPlanState) -> Dict[str, Any]:
#     """
#     auto_research：
#     - LLM 自动生成 3 组候选企业（每组 3 家）
#     - 中断流程，让用户选择一组
#     - 将选择结果写入 companies.target_names
#     """
#
#     print("\n--- 🤖 节点: auto_research ---")
#
#     # ========= 1️⃣ 调用 LLM 生成推荐企业 =========
#     city = state["locations"]["hotel"]["city"]
#     llm_result: List[List[str]] = generate_company_recommendations_by_llm(city=city)
#
#     if not llm_result:
#         return {
#             "control": {
#                 "error_message": "LLM 未能生成有效的企业推荐方案"
#             }
#         }
#
#     print("📌 LLM 推荐企业方案：")
#     for idx, group in enumerate(llm_result, 1):
#         print(f"  方案 {idx}: {group}")
#
#     # ========= 2️⃣ 中断，让用户选择 =========
#     selected_index = interrupt({
#         "type": "company_selection",
#         "title": "请选择一组要调研的企业，输入选项对应的索引值：",
#         "options": [
#             {
#                 "index": i,
#                 "companies": group
#             }
#             for i, group in enumerate(llm_result)
#         ]
#     })
#
#     if selected_index is None:
#         return {
#             "control": {
#                 "error_message": "用户未选择企业方案"
#             }
#         }
#
#     index_int = int(selected_index)
#     selected_companies = llm_result[index_int]
#
#     print(f"✅ 用户选择企业方案 {index_int + 1}: {selected_companies}")
#
#     # ========= 3️⃣ 写回 CompanyContext =========
#     return {
#         "companies": {
#             "target_names": selected_companies,
#             "candidates": []
#         },
#         "control": {
#             "error_message": None
#         }
#     }


def auto_research(state: TravelPlanState) -> Dict[str, Any]:
    print("\n--- 🤖 节点: auto_research ---")

    city = state["locations"]["hotel"]["city"]

    # 2. 获取候选列表
    all_candidates = generate_company_recommendations_by_llm(city=city)

    # 3. 触发中断
    # 在 CLI 环境下，执行到这里会挂起，等待外部输入 resume 值
    selected_names = interrupt({
        "type": "company_multi_selection",
        "title": f"""请从候选企业中选择，输入一个名称列表 (例如：["华为", "腾讯", "深信服"])""",
        #"message": all_candidates 由于封装成api时，message的类型要确定，所以这里先去掉
        "options": all_candidates
    })

    if not selected_names:
        return {"control": {"error_message": "未收到有效的企业选择"}}

    # 如果用户在 CLI 调试时传的是字符串（比如 "华为,腾讯"），我们做个兼容处理
    if isinstance(selected_names, str):
        selected_names = [n.strip() for n in selected_names.replace("，", ",").split(",")]

    print(f"✅ 节点收到用户输入: {selected_names}")

    # 5. 写入状态
    return {
        "companies": {
            "target_names": selected_names,
            "candidates": []
        }
    }


def skip_research(state: TravelPlanState) -> Dict[str, Any]:
    print("\n--- 🤖 节点: skip_research ---")
    print("用户选择不进行企业调研")
    return {
        "companies": {
            "target_names": [],
            "candidates": []
        },
        "control": {
            "error_message": None
        }
    }
