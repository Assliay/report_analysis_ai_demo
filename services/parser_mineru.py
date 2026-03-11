import os
import json
from magic_pdf.data.read_api import read_local_pdfs
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze

def parse_pdf_mineru(pdf_path: str, output_dir: str = "output"):
    """
    Parses a PDF file using MinerU (Magic-PDF) v1.x locally.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Read PDF using the new API
    datasets = read_local_pdfs(pdf_path)
    if not datasets:
        raise Exception("Failed to read PDF content via MinerU")
    
    ds = datasets[0] 
    
    # Analyze and Parse
    # For research reports, 'ocr' or 'txt' parse method is generally used.
    # We'll default to 'ocr' for maximum accuracy in table extraction.
    infer_result = ds.apply(doc_analyze, model_type="ocr")
        
    # Get Markdown
    markdown_content = infer_result.pipe_txt()
        
    return markdown_content

def parse_pdf_fallback(pdf_path: str):
    """
    A simple fallback parser using PyMuPDF if MinerU is not fully ready.
    """
    import pymupdf
    doc = pymupdf.open(pdf_path)
    text = ""
    for page in doc:
        text += f"\n--- Page {page.number + 1} ---\n" + page.get_text()
    return text
