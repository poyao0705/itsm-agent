"""
ITSM Agent Compliance Utils
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError
from openai import APIError, APITimeoutError
from .state import ComplianceState
from .schemas import RiskAnalysisResult
from .prompts import RISK_AGENT_SYSTEM_PROMPT


# Global tools
# gpt-5.1 for strong reasoning capabilities
# temperature=0 for deterministic results
LLM = ChatOpenAI(model="gpt-5.2", temperature=0, timeout=30)

# 1. Define the Template (Standard LangChain Style)
RISK_AGENT_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", "{system_rules}"),
        ("human", "Here is the code diff to analyze:\n\n{git_diff}\n\n{feedback}"),
    ]
)


def analyze_risk(state: ComplianceState) -> ComplianceState:
    """Analyze the risk of the code diff"""
    structured_llm = LLM.with_structured_output(RiskAnalysisResult)
    previous_error = state.error_msg
    current_retries = state.retry_count
    git_diff = state.git_diff

    feedback_text = (
        f"Previous attempt failed with error: {previous_error}"
        if previous_error
        else ""
    )

    chain = RISK_AGENT_PROMPT_TEMPLATE | structured_llm

    try:
        result = chain.invoke(
            {
                "system_rules": RISK_AGENT_SYSTEM_PROMPT,
                "git_diff": git_diff,
                "feedback": feedback_text,
            }
        )

        return {
            "retry_count": 0,
            "error_msg": None,
            "risk_data": result,
            "audit_log": state.audit_log
            + [f"Risk Analysis: {result.risk_score} - {result.risk_reason}"],
        }
    except (ValidationError, APIError, APITimeoutError) as e:
        return {
            "retry_count": current_retries + 1,
            "error_msg": str(e),
            "risk_data": None,
            "audit_log": state.audit_log + [f"Risk Analysis Failed: {str(e)}"],
        }


# def aggregate_results(state: ComplianceState) -> ComplianceState:
#     """ Aggregates results from all agents (Risk, etc.) into a final decision. """

#     # 1. Gather Data
#     risk = state.risk_data

#     # 2. Default Decision
#     status = "APPROVED"
#     summary = "Changes are compliant."
#     approvals = []

#     # 3. Aggregation Logic (The "Policy")
#     if risk:
#         if risk.risk_score == "HIGH":
#             status = "NEEDS_MANUAL_REVIEW"
#             summary = f"High Risk changes detected: {risk.risk_reason}"
#             approvals.append("MANAGER_APPROVAL")
#         elif risk.risk_score == "MEDIUM":
#             # For Medium, maybe we just warn, or require peer review
#             # status = "NEEDS_MANUAL_REVIEW"
#             summary = f"Medium Risk changes: {risk.risk_reason}"
#             approvals.append("PEER_REVIEW")

#     # 4. Return update
#     from .schemas import ComplianceResult
#     decision = ComplianceResult(
#         status=status,
#         summary=summary,
#         required_approvals=approvals
#     )

#     return {
#         "final_decision": decision,
#         "audit_log": state.audit_log + [f"Final Decision: {status}"]
#     }
