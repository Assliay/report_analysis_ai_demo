import asyncio
import httpx
import sys
import time

async def test_rag():
    url_upload = "http://localhost:8001/upload"
    files = {"file": open("/Users/moltbot/.openclaw/workspace/test_report.pdf", "rb")}
    
    print("🚀 [1] Sending upload request to RAG service...")
    sys.stdout.flush()
    
    # 1. 提交文件
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url_upload, files=files, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                task_id = data.get("task_id")
                print(f"✅ Upload Success! Task ID: {task_id}")
                
                # 2. 轮询状态
                print("⏳ [2] Polling for task status...")
                url_status = f"http://localhost:8001/status/{task_id}"
                
                while True:
                    status_resp = await client.get(url_status, timeout=10.0)
                    status_data = status_resp.json()
                    
                    state = status_data.get("status")
                    if state == "completed":
                        print("🎉 Task Completed!")
                        print(status_data.get("result"))
                        break
                    elif state == "failed":
                        print(f"❌ Task Failed: {status_data.get('error')}")
                        break
                    else:
                        print(f"   ... current status: {state}")
                    
                    await asyncio.sleep(5)
            else:
                print(f"❌ Failed to upload: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"❌ Error during request: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag())
