from langgraph.graph import StateGraph, START, END

from app.services.change_management.utils.schemas import AgentState
from app.services.change_management.utils.nodes import (
    node_read_pr_from_webhook,
    node_fetch_pr_info,
    node_analyze_jira_ticket_number,
)


# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("node_read_pr_from_webhook", node_read_pr_from_webhook)
workflow.add_node("node_fetch_pr_info", node_fetch_pr_info)
workflow.add_node("node_analyze_jira_ticket_number", node_analyze_jira_ticket_number)

# 3. Add Edges
workflow.add_edge(START, "node_read_pr_from_webhook")
workflow.add_edge("node_read_pr_from_webhook", "node_fetch_pr_info")
workflow.add_edge("node_fetch_pr_info", "node_analyze_jira_ticket_number")
workflow.add_edge("node_analyze_jira_ticket_number", END)

# 4. Compile
change_management_graph = workflow.compile()
