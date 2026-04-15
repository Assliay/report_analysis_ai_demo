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

import os
import time
import uuid
import sys
import asyncio
import concurrent.futures
from typing import List, Dict, Any
from opensearchpy import OpenSearch, helpers
from services.llm import get_completion, aget_completion
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
        
        # OpenSearch 客户端 (保持同步用于索引创建和写入，查询将逐步支持异步)
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

    async def _agenerate_enhanced_queries(self, original_query: str) -> List[str]:
        prompt = f"""作为资深金融分析师，将以下查询扩展为 3 个专业检索词。仅输出词语，换行分隔。查询：{original_query}"""
        try:
            res = await aget_completion(prompt, "Financial analyst.")
            return [q.strip() for q in res.split("\n") if q.strip()][:3]
        except Exception:
            return []

    async def _asingle_query(self, q: str, query_vector: List[float], idx: int, top_k: int, report_id: str) -> List[str]:
        """异步单路检索 (使用 run_in_executor 桥接同步驱动)"""
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
        
        loop = asyncio.get_event_loop()
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                response = await loop.run_in_executor(None, lambda: self.client.search(index=self.index_name, body=search_query))
                results = []
                for hit in response["hits"]["hits"]:
                    if "inner_hits" in hit:
                        for inner_key in hit["inner_hits"]:
                            for inner_hit in hit["inner_hits"][inner_key]["hits"]["hits"]:
                                src = inner_hit["_source"]
                                results.append(f"[Page {src.get('page_num', '?')}] {src.get('content', '')}")
                return results
            except Exception as e:
                if "429" in str(e) and attempt < max_attempts - 1:
                    await asyncio.sleep((attempt + 1) * 2)
                else:
                    print(f"❌ RAG Search Error: {e}")
                    break
        return []

    async def aquery(self, query_text: str, top_k: int = 5, report_id: str = None) -> str:
        print(f"🚀 RAG: Asyncio concurrent retrieval started...")
        sys.stdout.flush()
        
        # 并发执行：1. 扩展查询 2. 原始查询向量化
        enhanced_task = asyncio.create_task(self._agenerate_enhanced_queries(query_text))
        
        loop = asyncio.get_event_loop()
        vector_task = loop.run_in_executor(None, self.embeddings.embed_query, query_text)
        
        enhanced_queries, original_vector = await asyncio.gather(enhanced_task, vector_task)
        all_queries = [query_text] + enhanced_queries
        
        # 并发生成其余向量
        vector_tasks = [loop.run_in_executor(None, self.embeddings.embed_query, q) for q in enhanced_queries]
        other_vectors = await asyncio.gather(*vector_tasks)
        all_vectors = [original_vector] + other_vectors
        
        # 并发执行多路检索
        search_tasks = [self._asingle_query(q, all_vectors[i], i, top_k, report_id) for i, q in enumerate(all_queries)]
        search_results = await asyncio.gather(*search_tasks)
        
        all_context_pieces = []
        for res in search_results:
            all_context_pieces.extend(res)

        unique_pieces = list(dict.fromkeys(all_context_pieces))
        if not unique_pieces: return "未检索到相关内容。"
        
        print(f"📊 RAG: Recalled {len(unique_pieces)} pieces, reranking...")
        sys.stdout.flush()
        
        reranked = await self._arerank_documents(query_text, unique_pieces, top_k)
        return "\n\n---\n\n".join(reranked)

    async def _arerank_documents(self, query: str, context_pieces: List[str], top_k: int) -> List[str]:
        if not context_pieces: return []
        context_str = "\n\n".join([f"ID:{i} | {c[:400]}" for i, c in enumerate(context_pieces)])
        prompt = f"请按相关性精排片段。仅返回前 {top_k} 个 ID（如 0,1）。查询：{query}\n片段：\n{context_str}"
        try:
            res = await aget_completion(prompt, "Senior auditor.")
            ids = [int(i.strip()) for i in res.replace("ID:", "").split(",") if i.strip().isdigit()]
            return [context_pieces[idx] for idx in ids if 0 <= idx < len(context_pieces)][:top_k]
        except Exception: return context_pieces[:top_k]

    def query(self, query_text: str, top_k: int = 5, report_id: str = None) -> str:
        """同步包装器，兼容现有同步调用"""
        return asyncio.run(self.aquery(query_text, top_k, report_id))
