# graph.py
from langgraph.graph import StateGraph, END, START
from nodes.approval_gate import transport_approval_gate, user_select_research_mode, user_refine_itinerary
from nodes.final_report import plan_day_1_by_llm, plan_day_2_3_by_llm, build_final_itinerary_and_report
from nodes.geo_process import geocode_locations, geocode_companies
from nodes.input_check import check_constraints
from nodes.research_mode import custom_research, auto_research, skip_research
from nodes.route_plan import traffic_query, select_transport_by_llm, user_select_transport
from state import TravelPlanState



# --- 构建 LangGraph ---
def build_travel_graph() -> StateGraph:
    workflow = StateGraph(TravelPlanState)

    # 1. 添加节点 (Nodes)
    workflow.add_node("check_constraints", check_constraints)
    workflow.add_node("geocode_locations", geocode_locations)
    workflow.add_node("traffic_query", traffic_query)
    workflow.add_node("select_transport_by_llm", select_transport_by_llm)
    workflow.add_node("transport_approval_gate", transport_approval_gate)
    workflow.add_node("user_select_transport", user_select_transport)
    workflow.add_node("plan_day_1_by_llm", plan_day_1_by_llm)
    workflow.add_node("user_select_research_mode", user_select_research_mode)
    workflow.add_node("custom_research", custom_research)
    workflow.add_node("auto_research", auto_research)
    workflow.add_node("skip_research", skip_research)
    workflow.add_node("geocode_companies", geocode_companies)
    workflow.add_node("plan_day_2_3_by_llm", plan_day_2_3_by_llm)
    workflow.add_node("build_final_itinerary_and_report", build_final_itinerary_and_report)
    workflow.add_node("user_refine_itinerary", user_refine_itinerary)


    workflow.add_edge(START, "check_constraints")
    workflow.add_edge("check_constraints", "geocode_locations")
    workflow.add_edge("geocode_locations", "traffic_query")
    workflow.add_edge("traffic_query", "select_transport_by_llm")
    workflow.add_edge("select_transport_by_llm", "transport_approval_gate")
    #def transport_approval_gate(state: TravelPlanState) -> Command[Literal["plan_day_1_by_llm", "user_select_transport"]]
    workflow.add_edge("user_select_transport", "plan_day_1_by_llm")
    workflow.add_edge("plan_day_1_by_llm", "user_select_research_mode")
    #def user_select_research_mode(state: TravelPlanState) -> Command[Literal["custom_research", "auto_research", "skip_research"]]

    workflow.add_edge("custom_research", "geocode_companies")
    workflow.add_edge("auto_research", "geocode_companies")

    workflow.add_edge("geocode_companies", "plan_day_2_3_by_llm")
    workflow.add_edge("skip_research", "plan_day_2_3_by_llm")
    workflow.add_edge("plan_day_2_3_by_llm", "build_final_itinerary_and_report")

    workflow.add_edge("build_final_itinerary_and_report", "user_refine_itinerary")

    #def user_refine_itinerary(state: TravelPlanState) -> Command[Literal["build_final_itinerary_and_report", END]]

    return workflow

graph = build_travel_graph()
