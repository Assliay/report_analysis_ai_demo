from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union

class Evidence(BaseModel):
    text: str = Field(..., description="The original text snippet from the report used as evidence.")
    page_number: Optional[Union[int, str]] = Field(None, description="The page number where the evidence was found.")

class FinancialMetric(BaseModel):
    year: Union[str, int] = Field(..., description="The year for the metric (e.g., '2023E', 2024).")
    value: Any = Field(..., description="The value of the metric.")
    evidence: Evidence

class ResearchReport(BaseModel):
    title: str = Field(..., description="Title of the research report.")
    publication_date: Optional[str] = Field(None, description="Date when the report was published.")
    institution: Optional[str] = Field(None, description="The brokerage or research institution.")
    analyst: List[str] = Field(default_factory=list, description="Names of the analysts.")
    
    company_name: Optional[str] = Field(None, description="Name of the target company.")
    stock_code: Optional[str] = Field(None, description="Stock code of the target company.")
    rating: Optional[str] = Field(None, description="Investment rating (e.g., Buy, Hold).")
    target_price: Optional[str] = Field(None, description="Target price mentioned in the report.")
    
    revenue_forecasts: List[FinancialMetric] = Field(default_factory=list)
    net_profit_forecasts: List[FinancialMetric] = Field(default_factory=list)
    
    core_logic: str = Field(..., description="Summary of the core investment logic.")
    risk_warnings: str = Field(..., description="Summary of key risks.")
    
    extra_fields: Dict[str, Any] = Field(default_factory=dict, description="Generic container for additional extracted fields.")

class ExtractionResult(BaseModel):
    data: ResearchReport
    verification_status: str = Field(..., description="Status of the extraction (e.g., 'verified', 'flagged').")
    reasoning: str = Field(..., description="The agent's reasoning for the extraction and verification.")
