import os
import json
from magic_pdf.data.data_reader_factory import get_data_reader
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.config.enums import PRE_PROCESS_ENUM

def parse_pdf_mineru(pdf_path: str, output_dir: str = "output"):
    """
    Parses a PDF file using MinerU (Magic-PDF) locally.
    """
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.basename(pdf_path)
    file_name_pre = os.path.splitext(file_name)[0]
    
    # Read PDF
    data_reader = get_data_reader(pdf_path)
    pdf_bytes = data_reader.read()
    
    # Analyze and Parse
    # Note: MinerU requires models to be downloaded locally. 
    # This assumes models are already in the default path (~/.magic-pdf/models)
    ds = PymuDocDataset(pdf_bytes)
    
    if ds.classify() == PRE_PROCESS_ENUM.PAPER:
        infer_result = ds.apply(doc_analyze, model_type="vllm") # or 'ocr'
        # Get Markdown
        markdown_content = infer_result.pipe_txt()
    else:
        # Default fallback for reports
        infer_result = ds.apply(doc_analyze, model_type="ocr")
        markdown_content = infer_result.pipe_txt()
        
    return markdown_content

# Fallback implementation if magic-pdf is not fully configured (models missing)
def parse_pdf_fallback(pdf_path: str):
    """
    A simple fallback parser if MinerU is not fully ready.
    """
    import PyMuPDF
    doc = PyMuPDF.open(pdf_path)
    text = ""
    for page in doc:
        text += f"\n--- Page {page.number + 1} ---\n" + page.get_text()
    return text
