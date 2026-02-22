"""
Change Management Agent Graph.

Builds the LangGraph StateGraph for the change management workflow.
"""

from langgraph.graph import StateGraph, START, END

from app.services.change_management.state import AgentState
from app.services.change_management.context import Ctx
from app.services.change_management.nodes import (
    read_pr_from_webhook,
    fetch_pr_info,
    analyze_jira_ticket_number,
    jira_to_code_llm_analysis,
    policy_rule_analysis,
    post_pr_comment,
)


# 1. Initialize Graph with context schema
workflow = StateGraph(AgentState, context_schema=Ctx)

# 2. Add Nodes
workflow.add_node("read_pr_from_webhook", read_pr_from_webhook)
workflow.add_node("fetch_pr_info", fetch_pr_info)
workflow.add_node("analyze_jira_ticket_number", analyze_jira_ticket_number)
workflow.add_node("jira_to_code_llm_analysis", jira_to_code_llm_analysis)
workflow.add_node("policy_rule_analysis", policy_rule_analysis)
workflow.add_node("post_pr_comment", post_pr_comment)

# 3. Add Edges
workflow.add_edge(START, "read_pr_from_webhook")
workflow.add_edge("read_pr_from_webhook", "fetch_pr_info")
workflow.add_edge("fetch_pr_info", "analyze_jira_ticket_number")
workflow.add_edge("analyze_jira_ticket_number", "jira_to_code_llm_analysis")
workflow.add_edge("analyze_jira_ticket_number", "policy_rule_analysis")
workflow.add_edge("jira_to_code_llm_analysis", "post_pr_comment")
workflow.add_edge("policy_rule_analysis", "post_pr_comment")
workflow.add_edge("post_pr_comment", END)

# 4. Compile
change_management_graph = workflow.compile()
