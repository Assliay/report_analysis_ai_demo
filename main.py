import asyncio
import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.concurrency import run_in_threadpool
from core.agent import create_agent
from services.parser import parse_pdf
from services.parser_mineru import parse_pdf_mineru, parse_pdf_fallback
from services.vector_service import VectorService
from schemas.extraction import ExtractionResult
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Financial Report Analysis Engine")
agent = create_agent()

@app.post("/upload", response_model=ExtractionResult)
async def upload_report(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    # 异步写入文件，避免阻塞事件循环
    temp_id = str(uuid.uuid4())
    temp_path = f"temp_{temp_id}.pdf"
    
    # 获取文件内容
    content = await file.read()
    await run_in_threadpool(write_file_sync, temp_path, content)
    
    try:
        # 1. Parse PDF
        parser_type = os.getenv("PARSER_TYPE", "mineru")
        print(f"🚀 Step 1: Parsing {file.filename} using {parser_type}...")
        
        if parser_type == "mineru":
            try:
                # 尝试使用 MinerU v4 API (涉及大量同步 requests，交给线程池)
                markdown_content = await run_in_threadpool(parse_pdf_mineru, temp_path)
            except Exception as e:
                print(f"MinerU failed, falling back to basic PDF text: {e}")
                markdown_content = await run_in_threadpool(parse_pdf_fallback, temp_path)
        else:
            markdown_content = await run_in_threadpool(parse_pdf, temp_path)
        
        # 2. RAG Initialization
        print(f"✅ Step 2: Building Vector Store (Nested + RRF) for {file.filename}...")
        vector_db = VectorService()
        # Ingestion 涉及计算 Embedding 和网络请求，交给线程池
        await run_in_threadpool(
            vector_db.ingest_text, 
            markdown_content, 
            {"title": file.filename, "report_id": temp_id}
        )

        # 3. Run Agent workflow
        print(f"✅ Step 3: Running Agent Workflow with RAG...")
        initial_state = {
            "content": markdown_content,
            "report_id": temp_id,
            "vector_db": vector_db,
            "extraction": {},
            "iteration": 0,
            "feedback": "",
            "is_valid": False
        }
        
        # 触发 LangGraph 节点（底层包含 LiteLLM 调用），使用异步包装
        final_state = await run_in_threadpool(agent.invoke, initial_state)
        
        return {
            "data": final_state["extraction"],
            "verification_status": "verified" if final_state["is_valid"] else "needs_review",
            "reasoning": final_state["feedback"]
        }
        
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 异步清理文件
        await run_in_threadpool(cleanup_file_sync, temp_path)

def write_file_sync(path: str, data: bytes):
    with open(path, "wb") as f:
        f.write(data)

def cleanup_file_sync(path: str):
    if os.path.exists(path):
        os.remove(path)

if __name__ == "__main__":
    import uvicorn
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)
