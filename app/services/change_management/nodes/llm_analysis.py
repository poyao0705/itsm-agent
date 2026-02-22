"""Node for analyzing JIRA ticket description versus code changes using LLM in change management agent"""

from typing import Literal

from sqlmodel import SQLModel, Field

from app.core.logging import get_logger
from app.core.llm import default_llm
from app.services.change_management.state import AgentState
from app.services.change_management.prompts import SEMANTIC_RISK_AUDIT_PROMPT
from app.services.change_management.nodes.utils import make_result

logger = get_logger(__name__)

_NODE_NAME = "jira_to_code_llm_analysis"


class JIRAAnalysisOutput(SQLModel):
    """Structured output from the LLM semantic-risk audit."""

    risk_level: Literal["LOW", "UNKNOWN"] = Field(
        default="UNKNOWN",
        description="The risk level of the change based on JIRA analysis.",
    )
    reason: str = Field(
        default="",
        description="A concise summary of the findings from the JIRA analysis.",
    )


def _extract_jira_description(metadata: dict) -> str:
    """Extract human-readable description from JIRA issue metadata.

    Atlassian Document Format (ADF) stores text in nested content nodes.
    Falls back to the raw value if parsing fails.
    """
    fields = metadata.get("fields", {})
    desc = fields.get("description")

    if desc is None:
        return ""

    # Plain string (Server / older API)
    if isinstance(desc, str):
        return desc

    # Atlassian Document Format (Cloud)
    if isinstance(desc, dict):
        try:
            parts: list[str] = []
            for block in desc.get("content", []):
                for inline in block.get("content", []):
                    if inline.get("type") == "text":
                        parts.append(inline.get("text", ""))
            return "\n".join(parts)
        except (TypeError, AttributeError):
            return str(desc)

    return str(desc)


async def jira_to_code_llm_analysis(state: AgentState) -> dict:
    """Compare JIRA ticket description against code diff using an LLM.

    Returns an analysis result with risk_level LOW or UNKNOWN.
    """
    if not state.jira_ticket_number or not state.jira_ticket_metadata:
        logger.warning(
            "No JIRA ticket number or metadata found in state, skipping LLM analysis."
        )
        return make_result(
            node_name=_NODE_NAME,
            reason_code="JIRA_TO_CODE_LLM_ANALYSIS_SKIPPED",
            summary="[UNKNOWN RISK] LLM analysis skipped — missing JIRA ticket data.",
            risk_level="UNKNOWN",
            details={},
        )

    pr_info = state.pr_info or {}
    diff = pr_info.get("diff", "")
    if not diff:
        logger.warning("No diff available in pr_info, skipping LLM analysis.")
        return make_result(
            node_name=_NODE_NAME,
            reason_code="JIRA_TO_CODE_LLM_ANALYSIS_NO_DIFF",
            summary="[UNKNOWN RISK] LLM analysis skipped — no code diff available.",
            risk_level="UNKNOWN",
            details={},
        )

    jira_description = _extract_jira_description(state.jira_ticket_metadata)
    if not jira_description:
        logger.warning("JIRA ticket has no description, skipping LLM analysis.")
        return make_result(
            node_name=_NODE_NAME,
            reason_code="JIRA_TO_CODE_LLM_ANALYSIS_NO_DESCRIPTION",
            summary="[UNKNOWN RISK] LLM analysis skipped — JIRA ticket has no description.",
            risk_level="UNKNOWN",
            details={"jira_ticket_number": state.jira_ticket_number},
        )

    # Build the LLM chain with structured output
    llm = default_llm.with_structured_output(JIRAAnalysisOutput)
    chain = SEMANTIC_RISK_AUDIT_PROMPT | llm

    try:
        result = await chain.ainvoke(
            {
                "jira_ticket_description": jira_description,
                "diff": diff,
            }
        )
        if isinstance(result, dict):
            result = JIRAAnalysisOutput(**result)
    except Exception as e:
        logger.error("LLM analysis failed: %s", e, exc_info=True)
        return make_result(
            node_name=_NODE_NAME,
            reason_code="JIRA_TO_CODE_LLM_ANALYSIS_ERROR",
            summary="[UNKNOWN RISK] LLM analysis failed due to an error.",
            risk_level="UNKNOWN",
            details={"error": str(e)},
        )

    risk = result.risk_level
    reason = result.reason

    logger.info(
        "LLM analysis for %s: risk=%s reason=%s",
        state.jira_ticket_number,
        risk,
        reason,
    )

    return make_result(
        node_name=_NODE_NAME,
        reason_code="JIRA_TO_CODE_LLM_ANALYSIS_COMPLETE",
        summary=f"[{risk} RISK] {reason}",
        risk_level=risk,
        details={
            "jira_ticket_number": state.jira_ticket_number,
            "risk_level": risk,
            "reason": reason,
        },
    )
