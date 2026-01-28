from langgraph.graph import StateGraph, START, END

from app.services.change_management.utils.schemas import AgentState
from app.services.change_management.utils.nodes import (
    node_read_pr_from_webhook,
    node_fetch_pr_info,
)


# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("read_pr_from_webhook", node_read_pr_from_webhook)
workflow.add_node("fetch_pr_info", node_fetch_pr_info)

# 3. Add Edges
workflow.add_edge(START, "read_pr_from_webhook")
workflow.add_edge("read_pr_from_webhook", "fetch_pr_info")
workflow.add_edge("fetch_pr_info", END)

# 4. Compile
change_management_graph = workflow.compile()
