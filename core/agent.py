import json
from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from schemas.extraction import ResearchReport, ExtractionResult
from services.llm import get_completion

class AgentState(TypedDict):
    content: str  # The raw markdown content of the report
    extraction: dict
    iteration: int
    feedback: str
    is_valid: bool

def extraction_node(state: AgentState):
    """
    Extract structured data from the report content.
    """
    content = state["content"]
    prompt = f"""
    Based on the following financial research report content (in Markdown), extract the required information.
    Return a JSON object matching the ResearchReport schema.
    Ensure every metric has an 'evidence' field with the exact quote from the text and the page number.
    
    CONTENT:
    {content[:15000]}  # Truncate if too long
    """
    
    system_prompt = "You are a professional financial data extractor. Output ONLY valid JSON."
    
    result_json = get_completion(prompt, system_prompt)
    return {
        "extraction": json.loads(result_json),
        "iteration": state.get("iteration", 0) + 1
    }

def verification_node(state: AgentState):
    """
    Self-reflection node to verify the extraction accuracy.
    """
    extraction = state["extraction"]
    content = state["content"]
    
    prompt = f"""
    Review the following extracted data and the original content. 
    Verify if the evidence quoted actually exists and supports the extracted values.
    Check for:
    1. Accuracy of numbers.
    2. Correct attribution of years/dates.
    3. Proper page number referencing.
    
    EXTRACTED DATA:
    {json.dumps(extraction, indent=2)}
    
    Return a JSON object:
    {{
        "is_valid": boolean,
        "feedback": "Detailed explanation if invalid, else 'Verified'",
        "reasoning": "Internal thoughts"
    }}
    """
    
    verify_json = get_completion(prompt, "You are a senior financial auditor.")
    verify_res = json.loads(verify_json)
    
    return {
        "is_valid": verify_res["is_valid"],
        "feedback": verify_res["feedback"]
    }

def should_continue(state: AgentState):
    if state["is_valid"] or state["iteration"] >= 3:
        return END
    return "extract"

def create_agent():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("extract", extraction_node)
    workflow.add_node("verify", verification_node)
    
    workflow.set_entry_point("extract")
    workflow.add_edge("extract", "verify")
    workflow.add_conditional_edges(
        "verify",
        should_continue,
        {
            "extract": "extract",
            END: END
        }
    )
    
    return workflow.compile()
