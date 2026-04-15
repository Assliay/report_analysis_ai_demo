import json
from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from schemas.extraction import ResearchReport, ExtractionResult
from services.llm import get_completion
from services.vector_service import VectorService

class AgentState(TypedDict):
    content: str  # The raw markdown content of the report
    report_id: str # 加入 report_id 用于多并发时的隔离
    extraction: dict
    iteration: int
    feedback: str
    is_valid: bool
    vector_db: VectorService # 注入 RAG 服务

def extraction_node(state: AgentState):
    """
    RAG-Based Extract structured data from the report.
    """
    vector_db = state["vector_db"]
    
    # 针对 100 页研报采用多路检索 (Multi-query Retrieval) 策略
    # 1. 核心业务与逻辑
    logic_context = vector_db.query("核心逻辑, 业务模式, 投资建议, 行业地位, 竞争壁垒, 评级, 买入, 核心竞争力", top_k=6, report_id=state.get("report_id"))
    # 2. 财务关键指标与预测 (如 2023E, 2024E, 营收, 利润)
    finance_context = vector_db.query("营业收入, 净利润, EPS, 财务预测, 2023E, 2024E, 2025E, 毛利率", top_k=10, report_id=state.get("report_id"))
    # 3. 风险预警
    risk_context = vector_db.query("风险提示, 宏观风险, 下行风险, 行业竞争, 经营压力", top_k=4, report_id=state.get("report_id"))

    # 4. 全文关键字搜索 (针对研报标题/评级等核心元数据)
    meta_context = vector_db.query("标题, 评级, 目标价, EPS 预测, 核心逻辑", top_k=2, report_id=state.get("report_id"))
    
    combined_context = f"--- 核心元数据 ---\n{meta_context}\n\n--- 业务核心逻辑 ---\n{logic_context}\n\n--- 财务预测详情 ---\n{finance_context}\n\n--- 风险因素 ---\n{risk_context}"

    prompt = f"""
    Based on the following financial report snippets (RAG context), extract information.
    Return a JSON object matching the ResearchReport schema.
    
    CRITICAL: 
    - The output MUST be a valid JSON.
    - Fields 'title', 'target' (the company being researched), 'core_logic', and 'risk_warnings' are REQUIRED and MUST be strings.
    - Ensure 'title' is the actual report title, and 'target' specifically extracts the name of the subject/company of the report.
    - Do NOT return arrays for 'core_logic' or 'risk_warnings'; summarize them into a single string.
    - MUST provide 'evidence' for metrics with the EXACT quote and page number.
    
    RETRIEVED CONTEXT:
    {combined_context}
    """
    
    system_prompt = "You are a professional financial analyst. Output ONLY valid JSON."
    
    result_json = get_completion(prompt, system_prompt)
    
    # 清理 DeepSeek 有时会吐出的 Markdown 代码块标记
    clean_json = result_json.replace("```json", "").replace("```", "").strip()
    
    return {
        "extraction": json.loads(clean_json),
        "iteration": state.get("iteration", 0) + 1
    }

def verification_node(state: AgentState):
    """
    Self-reflection node: Verify the accuracy via vector database.
    """
    extraction = state["extraction"]
    vector_db = state["vector_db"]
    
    # 从提取出的 JSON 中抽取关键财务数值进行二次核对
    test_quotes = []
    for forecast in extraction.get("revenue_forecasts", []):
        quote = forecast.get("evidence", {}).get("text", "")
        if quote: test_quotes.append(quote)
    
    verify_context = ""
    if test_quotes:
        verify_context = vector_db.query(" ".join(test_quotes[:3]), top_k=4, report_id=state.get("report_id"))
    
    prompt = f"""
    Review the following extracted data and the original context. 
    Verify if the evidence quoted actually exists and supports the extracted values.
    
    EXTRACTED DATA:
    {json.dumps(extraction, indent=2)}
    
    ORIGINAL CONTEXT VERIFICATION:
    {verify_context}
    
    Return a JSON object:
    {{
        "is_valid": boolean,
        "feedback": "Detailed feedback if invalid, else 'Verified'",
        "reasoning": "Internal thoughts"
    }}
    """
    
    verify_json = get_completion(prompt, "You are a senior financial auditor. Output ONLY valid JSON.")
    clean_verify = verify_json.replace("```json", "").replace("```", "").strip()
    verify_res = json.loads(clean_verify)
    
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
