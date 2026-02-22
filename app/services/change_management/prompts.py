"""
Prompts for the Change Management LLM nodes.
"""

from langchain_core.prompts import PromptTemplate

# This prompt instructs the LLM to act as an ISO 20000 Auditor
# and compares the stated intent (JIRA Ticket Description) against the actual code changes.
SEMANTIC_RISK_AUDIT_PROMPT = PromptTemplate.from_template(
    """
    You are an air-gapped ISO 20000 ITIL Change Auditor. 
    Your job is to analyze the following code diff and JIRA ticket description to ensure compliance, 
    prevent scope creep, and identify unhandled risks.
    
    JIRA Ticket Description: {jira_ticket_description}
    
    Code Diff:
    {diff}

    Please evaluate the following:
    1. Alignment: Does the code diff strictly align with the stated intent in the JIRA ticket description? Are there hidden features or "scope creep"?
    2. Destructive Actions: Does this change introduce any destructive database actions, infrastructure changes, or unhandled security risks?

    Respond in JSON format with the following keys, if any of the criteria are not fully met, the risk level should be "UNKNOWN". Only if they are clearly met with no concerns should it be "LOW".:
    - "risk_level": string (one of "LOW", "UNKNOWN")
    - "reason": string (A concise summary of your findings)
    """
)
