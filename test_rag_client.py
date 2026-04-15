import asyncio
import httpx
import sys

async def test_rag():
    url = "http://localhost:8001/upload"
    files = {"file": open("/Users/moltbot/.openclaw/workspace/test_report.pdf", "rb")}
    
    print("🚀 Sending request to RAG service (this may take a few minutes)...")
    sys.stdout.flush()
    
    # 设置超长超时时间（10分钟）
    timeout = httpx.Timeout(600.0, connect=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, files=files)
            if response.status_code == 200:
                print("✅ Success!")
                print(response.json())
            else:
                print(f"❌ Failed: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"❌ Error during request: {e}")

if __name__ == "__main__":
    asyncio.run(test_rag())
