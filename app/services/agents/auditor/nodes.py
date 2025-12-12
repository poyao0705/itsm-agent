from langchain_openai import ChatOpenAI
# from langgraph.types import Command
from .state import ComplianceState
from .schemas import RiskAnalysisResult
from .prompts import AUDITOR_SYSTEM_PROMPT

# Global tools
# gpt-5.1 for strong reasoning capabilities
# temperature=0 for deterministic results
LLM = ChatOpenAI(model="gpt-5.1", temperature=0)

# 1. Define the Template (Standard LangChain Style)
# This replaces the manual `messages = [...]` list construction
AUDITOR_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", "{system_rules}"),
    ("human", "Here is the code diff to analyze:\n\n{git_diff}\n\n{feedback}"),
])

def analyze_risk(state: ComplianceState) -> ComplianceState:
    """ Analyze the risk of the code diff using LLM """ 
    structured_llm = LLM.with_structured_output(RiskAnalysisResult)
    previous_error = state.error_msg
    current_retries = state.retry_count
    git_diff = state.git_diff

    feedback_text = f"Previous attempt failed with error: {previous_error}" if previous_error else ""

    chain = AUDITOR_PROMPT_TEMPLATE | structured_llm

    try:
        result = chain.invoke({
            "system_rules": AUDITOR_SYSTEM_PROMPT,
            "git_diff": git_diff,
            "feedback": feedback_text,
        })

        return {
            "retry_count": 0,
            "error_msg": None,
            "risk_data": result,
            "audit_log": state.audit_log + [f"Risk Analysis: {result.risk_score} - {result.risk_reason}"]
        }
    except Exception as e:
        return {
            "retry_count": current_retries + 1,
            "error_msg": str(e),
            "risk_data": None,
            "audit_log": state.audit_log + [f"Risk Analysis Failed: {str(e)}"]
        }