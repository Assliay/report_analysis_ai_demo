import os
import requests
import time
import urllib3
import sys
import json

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_pdf_mineru(pdf_path: str):
    """
    使用 MinerU Agent 专属签名上传接口进行解析 (api/v1/agent)
    支持本地文件直接上传至 OSS 后解析。
    """
    api_key = os.getenv("MINERU_API_KEY")
    if not api_key:
        raise Exception("MINERU_API_KEY not found in environment variables")

    # 按照老大提供的最新示例，使用 v1/agent 路径
    BASE_URL = "https://mineru.net/api/v1/agent"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    try:
        file_name = os.path.basename(pdf_path)
        print(f"🚀 [MinerU Agent] 正在申请签名上传通道: {file_name}")
        sys.stdout.flush()

        # 1. 获取签名上传 URL
        data = {
            "file_name": file_name,
            "language": "ch",
            "enable_table": True,
            "is_ocr": False,
            "enable_formula": True
        }
        
        resp = requests.post(f"{BASE_URL}/parse/file", headers=headers, json=data, timeout=30)
        result = resp.json()
        
        if result.get("code") != 0:
            raise Exception(f"获取上传链接失败: {result.get('msg')}")

        task_id = result["data"]["task_id"]
        upload_url = result["data"]["file_url"]
        print(f"✅ [MinerU Agent] 任务已创建, task_id: {task_id}")
        sys.stdout.flush()

        # 2. PUT 上传文件到 OSS
        print(f"⏳ [MinerU Agent] 正在推送文件到云端存储...")
        sys.stdout.flush()
        with open(pdf_path, "rb") as f:
            # 注意：PUT 到 OSS 预签名 URL 通常不传 Auth Header，或者根据报错动态调整
            put_resp = requests.put(upload_url, data=f, timeout=120)
            if put_resp.status_code not in (200, 201):
                raise Exception(f"文件推送 OSS 失败: HTTP {put_resp.status_code}")
        
        print("✅ [MinerU Agent] 文件上传成功，启动云端解析...")
        sys.stdout.flush()

        # 3. 轮询等待结果
        return _poll_agent_result(BASE_URL, task_id, headers)

    except Exception as e:
        print(f"⚠️ [MinerU Agent] 链路异常: {e}, 自动回退本地解析...")
        sys.stdout.flush()
        return parse_pdf_fallback(pdf_path)

def _poll_agent_result(base_url, task_id, headers, timeout=300, interval=5):
    """轮询 Agent 接口结果"""
    state_labels = {
        "pending": "排队中",
        "running": "解析中",
        "waiting-file": "等待文件上传",
    }
    start = time.time()
    
    print(f"⏳ [MinerU Agent] 正在等待解析结果...")
    sys.stdout.flush()
    
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{base_url}/parse/{task_id}", headers=headers, timeout=10)
            result = resp.json()
            
            if result.get("code") != 0:
                print(f"   ...轮询接口暂无数据 (code: {result.get('code')})")
                time.sleep(interval)
                continue
                
            task_data = result.get("data", {})
            state = task_data.get("state")
            elapsed = int(time.time() - start)

            if state == "done":
                markdown_url = task_data.get("markdown_url")
                print(f"✅ [MinerU Agent] {elapsed}s 解析完成, 正在拉取 Markdown 内容...")
                md_resp = requests.get(markdown_url, timeout=30)
                return md_resp.text

            if state == "failed":
                raise Exception(f"云端解析失败: {task_data.get('err_msg', '未知错误')}")

            print(f"   [{elapsed}s] 状态: {state_labels.get(state, state)}...")
            sys.stdout.flush()
            
        except Exception as poll_e:
            print(f"   ...轮询异常: {poll_e}")
            
        time.sleep(interval)

    raise Exception(f"轮询超时 ({timeout}s)")

def parse_pdf_fallback(pdf_path: str):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    text = ""
    for page in doc:
        text += f"\n--- Page {page.number + 1} ---\n" + page.get_text()
    return text
