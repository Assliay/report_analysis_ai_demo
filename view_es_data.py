import os
import json
from dotenv import load_dotenv
from opensearchpy import OpenSearch

# 禁用不安全请求警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def view_opensearch_data():
    load_dotenv("/Users/moltbot/Desktop/report_analysis/.env")
    es_url = os.getenv("ELASTICSEARCH_URL")
    index_name = os.getenv("ES_INDEX_NAME", "financial_reports_v2")

    client = OpenSearch(
        [es_url],
        use_ssl=True,
        verify_certs=False,
        ssl_show_warn=False
    )

    print(f"🔍 正在连接云端 OpenSearch 查询索引: {index_name} ...\n")

    # 查询 1 条完整文档，排除庞大的 vector 向量数据以便于阅读
    query = {
        "size": 1,
        "_source": {
            "excludes": ["chunks.vector"] 
        },
        "query": {
            "match_all": {}
        }
    }

    try:
        response = client.search(index=index_name, body=query)
        hits = response.get("hits", {}).get("hits", [])
        
        if not hits:
            print("⚠️ 索引中目前没有数据。")
            return

        doc = hits[0]
        source = doc["_source"]
        chunks = source.get("chunks", [])

        print("=========================================")
        print(f"📄 研报 ID (Document ID) : {doc['_id']}")
        print(f"📑 研报标题 (Title)      : {source.get('title')}")
        print(f"🧩 嵌套切片数量 (Chunks) : {len(chunks)} 个")
        print("=========================================\n")

        if chunks:
            print("👇 提取第一个切片 (Chunk) 的内容示例：")
            sample_chunk = chunks[0]
            print(json.dumps(sample_chunk, indent=4, ensure_ascii=False))

    except Exception as e:
        print(f"❌ 查询失败: {e}")

if __name__ == "__main__":
    view_opensearch_data()
