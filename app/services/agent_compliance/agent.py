from langgraph.graph import StateGraph, START, END
from .utils.state import ComplianceState
from .utils.nodes import analyze_risk

# 1. Initialize Graph
workflow = StateGraph(ComplianceState)

# 2. Add Nodes
workflow.add_node("risk_analysis", analyze_risk)
# workflow.add_node("aggregation", aggregate_results)

# 3. Add Edges
# START -> Risk Analysis -> Aggregation -> END
workflow.add_edge(START, "risk_analysis")
# workflow.add_edge("risk_analysis", "aggregation")
workflow.add_edge("risk_analysis", END)

# 4. Compile
compliance_graph = workflow.compile()
