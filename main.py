import asyncio
import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
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

# 简单的内存任务状态存储 (生产环境建议用 Redis 或 DB)
TASKS = {}

async def process_pdf_task(task_id: str, temp_path: str, filename: str):
    """后台处理 PDF 的异步任务"""
    TASKS[task_id]["status"] = "processing"
    try:
        # 1. Parse PDF
        parser_type = os.getenv("PARSER_TYPE", "mineru")
        print(f"🚀 Task {task_id} Step 1: Parsing {filename} using {parser_type}...")
        
        if parser_type == "mineru":
            try:
                markdown_content = await run_in_threadpool(parse_pdf_mineru, temp_path)
            except Exception as e:
                print(f"MinerU failed, falling back to basic PDF text: {e}")
                markdown_content = await run_in_threadpool(parse_pdf_fallback, temp_path)
        else:
            markdown_content = await run_in_threadpool(parse_pdf, temp_path)
        
        # 2. RAG Initialization
        print(f"✅ Task {task_id} Step 2: Building Vector Store (Nested + RRF) for {filename}...")
        vector_db = VectorService()
        await run_in_threadpool(
            vector_db.ingest_text, 
            markdown_content, 
            {"title": filename, "report_id": task_id}
        )

        # 3. Run Agent workflow
        print(f"✅ Task {task_id} Step 3: Running Agent Workflow with RAG...")
        initial_state = {
            "content": markdown_content,
            "report_id": task_id,
            "vector_db": vector_db,
            "extraction": {},
            "iteration": 0,
            "feedback": "",
            "is_valid": False
        }
        
        final_state = await agent.ainvoke(initial_state)
        
        TASKS[task_id]["status"] = "completed"
        TASKS[task_id]["result"] = {
            "data": final_state["extraction"],
            "verification_status": "verified" if final_state["is_valid"] else "needs_review",
            "reasoning": final_state["feedback"]
        }
        print(f"🎉 Task {task_id} Completed!")
        
    except Exception as e:
        print(f"❌ Task {task_id} Error: {e}")
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)
    finally:
        # 清理临时文件
        await run_in_threadpool(cleanup_file_sync, temp_path)

@app.post("/upload")
async def upload_report(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """接收文件，立即返回 Task ID"""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    
    task_id = str(uuid.uuid4())
    temp_path = f"temp_{task_id}.pdf"
    
    # 获取并写入文件
    content = await file.read()
    await run_in_threadpool(write_file_sync, temp_path, content)
    
    # 初始化任务状态
    TASKS[task_id] = {"status": "pending", "result": None, "error": None}
    
    # 将处理逻辑加入 FastAPI 的后台任务队列
    background_tasks.add_task(process_pdf_task, task_id, temp_path, file.filename)
    
    return {"task_id": task_id, "status": "pending", "message": "File uploaded successfully. Processing started in background."}

@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """根据 Task ID 轮询结果"""
    if task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Task not found")
    return TASKS[task_id]

@app.websocket("/ws/status/{task_id}")
async def websocket_status(websocket: WebSocket, task_id: str):
    """WebSocket 实时推送任务状态"""
    await websocket.accept()
    if task_id not in TASKS:
        await websocket.send_json({"error": "Task not found"})
        await websocket.close()
        return

    try:
        last_status = None
        while True:
            current_status = TASKS[task_id]["status"]
            if current_status != last_status:
                await websocket.send_json(TASKS[task_id])
                last_status = current_status
            
            if current_status in ["completed", "failed"]:
                break
                
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for task {task_id}")
    finally:
        if not websocket.client_state.name == "DISCONNECTED":
            await websocket.close()

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
