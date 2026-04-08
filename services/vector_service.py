import os
import time
import uuid
import sys
import concurrent.futures
from typing import List, Dict, Any
from opensearchpy import OpenSearch, helpers
from services.llm import get_completion
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

class VectorService:
    def __init__(self):
        self.model_name = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self.embeddings = OpenAIEmbeddings(
            model=self.model_name,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE")
        )
        
        self.es_url = os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
        self.index_name = os.getenv("ES_INDEX_NAME", "financial_reports_v2")
        
        # OpenSearch 认证处理 (Bonsai 兼容性)
        self.client = OpenSearch(
            [self.es_url],
            http_auth=None,
            use_ssl=True,
            verify_certs=False,
            ssl_show_warn=False
        )
        self._ensure_index()

    def _ensure_index(self):
        """兼容 OpenSearch (Bonsai) 的原生索引映射"""
        if self.client.indices.exists(index=self.index_name):
            return

        settings = {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "refresh_interval": "1s",
                "knn": True 
            }
        }
        
        mappings = {
            "properties": {
                "report_id": {"type": "keyword"},
                "title": {"type": "text"},
                "chunks": {
                    "type": "nested",
                    "properties": {
                        "content": {
                            "type": "text",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "vector": {
                            "type": "knn_vector",
                            "dimension": 1024,
                            "method": {
                                "name": "hnsw",
                                "space_type": "cosinesimil",
                                "engine": "nmslib"
                            }
                        },
                        "page_num": {"type": "integer"},
                        "chunk_id": {"type": "keyword"}
                    }
                }
            }
        }
        
        try:
            self.client.indices.create(index=self.index_name, body={"settings": settings, "mappings": mappings})
            print(f"✅ RAG: OpenSearch 索引 {self.index_name} 已就绪")
            sys.stdout.flush()
        except Exception as e:
            print(f"❌ Index creation failed: {e}")
            sys.stdout.flush()

    def ingest_text(self, text: str, metadata: Dict[str, Any] = None):
        """以 Nested 结构入库"""
        report_id = metadata.get("report_id", str(uuid.uuid4()))
        title = metadata.get("title", "Unknown Report")
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n# ", "\n## ", "\n### ", "\n\n", "\n", " "]
        )
        documents = splitter.create_documents([text])
        
        print(f"RAG: 开始分片入库 {len(documents)} 个片段...")
        sys.stdout.flush()
        chunks_data = []
        
        # 向量生成加速：使用并发加速
        batch_size = 16
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_batch = {
                executor.submit(self.embeddings.embed_documents, [d.page_content for d in documents[i : i + batch_size]]): i 
                for i in range(0, len(documents), batch_size)
            }
            for future in concurrent.futures.as_completed(future_to_batch):
                i = future_to_batch[future]
                try:
                    batch_vectors = future.result()
                    batch_docs = documents[i : i + batch_size]
                    for j, doc in enumerate(batch_docs):
                        chunks_data.append({
                            "chunk_id": f"{report_id}_{i+j}",
                            "content": doc.page_content,
                            "vector": batch_vectors[j],
                            "page_num": i + j + 1
                        })
                    print(f"RAG: 已完成第 {i} 批向量生成")
                    sys.stdout.flush()
                except Exception as e:
                    print(f"❌ Batch embedding error: {e}")

        parent_doc = {
            "report_id": report_id,
            "title": title,
            "chunks": chunks_data
        }

        print(f"RAG: 正在写入云端 OpenSearch...")
        sys.stdout.flush()
        self.client.index(index=self.index_name, id=report_id, body=parent_doc, refresh=True)
        print(f"✅ RAG: 成功入库研报 '{title}'")
        sys.stdout.flush()

    def _generate_enhanced_queries(self, original_query: str) -> List[str]:
        prompt = f"""作为资深金融分析师，将以下查询扩展为 3 个专业检索词。仅输出词语，换行分隔。查询：{original_query}"""
        try:
            res = get_completion(prompt, "Financial analyst.")
            return [q.strip() for q in res.split("\n") if q.strip()][:3]
        except Exception:
            return []

    def _single_query(self, q: str, query_vector: List[float], idx: int, top_k: int, report_id: str) -> List[str]:
        """单路检索逻辑 (包含 429 重试机制)"""
        search_query = {
            "size": top_k,
            "query": {
                "bool": {
                    "should": [
                        {"nested": {"path": "chunks", "query": {"match": {"chunks.content": q}}, "inner_hits": {"name": f"bm25_{idx}", "_source": ["chunks.content", "chunks.page_num"], "size": 3}}},
                        {"nested": {"path": "chunks", "query": {"knn": {"chunks.vector": {"vector": query_vector, "k": top_k}}}, "inner_hits": {"name": f"knn_{idx}", "_source": ["chunks.content", "chunks.page_num"], "size": 3}}}
                    ]
                }
            }
        }
        if report_id: search_query["query"]["bool"]["filter"] = [{"term": {"report_id": report_id}}]
        
        results = []
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = self.client.search(index=self.index_name, body=search_query)
                for hit in response["hits"]["hits"]:
                    if "inner_hits" in hit:
                        for inner_key in hit["inner_hits"]:
                            for inner_hit in hit["inner_hits"][inner_key]["hits"]["hits"]:
                                src = inner_hit["_source"]
                                results.append(f"[Page {src.get('page_num', '?')}] {src.get('content', '')}")
                break # 成功则退出
            except Exception as e:
                if "429" in str(e) and attempt < max_attempts - 1:
                    wait = (attempt + 1) * 2
                    print(f"⚠️ RAG Search 429 hit, retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"❌ RAG Search Error: {e}")
                    break
        return results

    def query(self, query_text: str, top_k: int = 5, report_id: str = None) -> str:
        print(f"🔍 RAG: 并发检索启动...")
        sys.stdout.flush()
        
        all_enhanced = [query_text] + self._generate_enhanced_queries(query_text)
        
        # 1. 并发生成所有 Query 的 Embedding
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(all_enhanced)) as executor:
            vectors = list(executor.map(self.embeddings.embed_query, all_enhanced))
        
        # 2. 并发执行多路检索 (减少 worker 数量以应对 Bonsai 429)
        all_context_pieces = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self._single_query, q, vectors[i], i, top_k, report_id) for i, q in enumerate(all_enhanced)]
            for future in concurrent.futures.as_completed(futures):
                all_context_pieces.extend(future.result())

        unique_pieces = list(dict.fromkeys(all_context_pieces))
        if not unique_pieces: return "未检索到相关内容。"
        
        print(f"📊 RAG: 召回 {len(unique_pieces)} 个片段，进入精排...")
        sys.stdout.flush()
        return "\n\n---\n\n".join(self._rerank_documents(query_text, unique_pieces, top_k))

    def _rerank_documents(self, query: str, context_pieces: List[str], top_k: int) -> List[str]:
        if not context_pieces: return []
        context_str = "\n\n".join([f"ID:{i} | {c[:400]}" for i, c in enumerate(context_pieces)])
        prompt = f"请按相关性精排片段。仅返回前 {top_k} 个 ID（如 0,1）。查询：{query}\n片段：\n{context_str}"
        try:
            res = get_completion(prompt, "Senior auditor.")
            ids = [int(i.strip()) for i in res.replace("ID:", "").split(",") if i.strip().isdigit()]
            return [context_pieces[idx] for idx in ids if 0 <= idx < len(context_pieces)][:top_k]
        except Exception: return context_pieces[:top_k]
