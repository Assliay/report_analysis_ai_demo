import os
from llama_parse import LlamaParse
from dotenv import load_dotenv

load_dotenv()

def parse_pdf(file_path: str):
    """
    Parses a PDF file using LlamaParse into Markdown.
    """
    parser = LlamaParse(
        result_type="markdown",
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        verbose=True,
        language="ch"  # Support Chinese
    )
    
    documents = parser.load_data(file_path)
    # Combine all pages into one text or handle page by page
    full_text = ""
    for idx, doc in enumerate(documents):
        full_text += f"\n--- Page {idx + 1} ---\n" + doc.text
        
    return full_text
