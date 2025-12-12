from langchain_openai import ChatOpenAI
from langgraph.types import Command

# gpt-5.1 for strong reasoning capabilities
# temperature=0 for deterministic results
llm = ChatOpenAI(model="gpt-5.1", temperature=0)

def analyze_risk(state: AuditorState) -> AuditorState:
    pass