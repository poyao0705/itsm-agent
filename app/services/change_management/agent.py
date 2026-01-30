from langgraph.graph import StateGraph, START, END

from app.services.change_management.utils.schemas import AgentState
from app.services.change_management.utils.nodes import (
    node_read_pr_from_webhook,
    node_fetch_pr_info,
    node_analyze_jira_ticket_number,
    node_post_pr_comment,
    node_analyze_code_diff_hard,
)


# 1. Initialize Graph
workflow = StateGraph(AgentState)

# 2. Add Nodes
workflow.add_node("node_read_pr_from_webhook", node_read_pr_from_webhook)
workflow.add_node("node_fetch_pr_info", node_fetch_pr_info)
workflow.add_node("node_analyze_jira_ticket_number", node_analyze_jira_ticket_number)
workflow.add_node("node_analyze_code_diff_hard", node_analyze_code_diff_hard)
workflow.add_node("node_post_pr_comment", node_post_pr_comment)

# 3. Add Edges
workflow.add_edge(START, "node_read_pr_from_webhook")
workflow.add_edge("node_read_pr_from_webhook", "node_fetch_pr_info")
workflow.add_edge("node_fetch_pr_info", "node_analyze_jira_ticket_number")
workflow.add_edge("node_analyze_jira_ticket_number", "node_analyze_code_diff_hard")
workflow.add_edge("node_analyze_code_diff_hard", "node_post_pr_comment")
workflow.add_edge("node_post_pr_comment", END)

# 4. Compile
change_management_graph = workflow.compile()
