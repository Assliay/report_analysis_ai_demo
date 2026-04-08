import os
import requests
import json
import time

def run_test(pdf_name):
    url = "http://127.0.0.1:8000/upload"
    pdf_path = f"/tmp/test_reports/{pdf_name}"
    
    if not os.path.exists(pdf_path):
        return {"error": f"File {pdf_name} not found"}
        
    print(f"🚀 Testing {pdf_name}...")
    files = {'file': open(pdf_path, 'rb')}
    try:
        # 增加超时时间，MinerU 远程解析较慢
        response = requests.post(url, files=files, timeout=300)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def main():
    reports = ["report_1.pdf", "report_2.pdf", "report_3.pdf", "report_4.pdf"]
    all_results = {}
    
    for report in reports:
        result = run_test(report)
        all_results[report] = result
        # 打印简要结果
        status = result.get("verification_status", "failed")
        title = result.get("data", {}).get("title", "N/A")
        print(f"✅ {report} Done. Status: {status}, Title: {title}")
        time.sleep(2) # 避免瞬间请求过载

    output_path = "/Users/moltbot/Desktop/report_analysis_test_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✨ All tests completed. Results saved to {output_path}")

if __name__ == "__main__":
    main()
