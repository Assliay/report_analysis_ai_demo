import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from core.agent import create_agent
from services.parser import parse_pdf
from services.parser_mineru import parse_pdf_mineru, parse_pdf_fallback
from schemas.extraction import ExtractionResult
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Financial Report Analysis Engine")
agent = create_agent()

@app.post("/upload", response_model=ExtractionResult)
async def upload_report(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # Save temporary file
    temp_id = str(uuid.uuid4())
    temp_path = f"temp_{temp_id}.pdf"
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. Parse PDF
        parser_type = os.getenv("PARSER_TYPE", "llamaparse")
        print(f"Parsing {file.filename} using {parser_type}...")
        
        if parser_type == "mineru":
            try:
                markdown_content = parse_pdf_mineru(temp_path)
            except Exception as e:
                print(f"MinerU failed, falling back to basic PDF text: {e}")
                markdown_content = parse_pdf_fallback(temp_path)
        else:
            markdown_content = parse_pdf(temp_path)
        
        # 2. Run Agent workflow
        print(f"Running Agent Workflow...")
        initial_state = {
            "content": markdown_content,
            "extraction": {},
            "iteration": 0,
            "feedback": "",
            "is_valid": False
        }
        
        final_state = agent.invoke(initial_state)
        
        return {
            "data": final_state["extraction"],
            "verification_status": "verified" if final_state["is_valid"] else "needs_review",
            "reasoning": final_state["feedback"]
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
