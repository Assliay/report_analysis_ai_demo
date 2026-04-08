import requests
import os

def test_upload():
    url = "http://127.0.0.1:8000/upload"
    file_path = "/Users/moltbot/Desktop/report_analysis/test_report.pdf"
    
    if not os.path.exists(file_path):
        print(f"Error: Test file {file_path} not found.")
        return

    print(f"Uploading {file_path} to {url}...")
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "application/pdf")}
        try:
            response = requests.post(url, files=files, timeout=300)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                print("Extraction Result:")
                import json
                print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            else:
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    test_upload()
