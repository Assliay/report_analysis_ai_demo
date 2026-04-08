# 金融研报分析 AI 引擎 (Financial Report Analysis AI Engine)

基于 Agentic RAG（检索增强生成）与多路混合检索架构的金融长文档自动化分析系统。专为处理长达 100+ 页的金融研究报告设计，具备高精度的指标提取、数据核对溯源与自动降级保护能力。

## 🎯 核心能力 (Core Features)

1. **多擎混合解析 (Multi-engine Parser)**
   - 首选：**MinerU Agent 专属通道 (v1/agent)**，支持 PDF 流式上传与云端智能分片。
   - 极速兜底：**PyMuPDF 本地引擎**，当云端拒绝或网络异常时，在 1 秒内无感降级，提取纯文本。
2. **原生 Elasticsearch / OpenSearch RAG**
   - **Nested Mapping (父子文档)**：一份 PDF 对应一个顶层文档，切片作为子对象存储，确保检索结果与原文结构的物理级绑定。
   - **Hybrid Search (混合检索)**：利用原生 ES DSL，结合 BM25 关键字（金融术语强匹配）与 kNN 向量检索（逻辑语义）。
   - **Pre-filtering (数据隔离)**：在 RAG 检索前对 `report_id` 进行硬过滤，彻底杜绝跨文档的内容污染。
3. **Advanced RAG 检索增强链路**
   - **提问增强 (Multi-Query)**：通过 LLM 将单一问题扩展为 3 个专业检索词（覆盖财报年份、核心指标等维度）。
   - **并发加速**：基于 `ThreadPoolExecutor` 的多线程并发架构，实现多路召回与向量化处理的毫秒级提速。
   - **LLM Rerank (精排)**：引入“高级审计员”节点，对召回的 Top-N 切片进行事实对齐排序，去除高向量分但逻辑不相关的噪音。
4. **LangGraph 智能体审核流**
   - 提取（Extraction）：生成符合 `ResearchReport` Pydantic Schema 的结构化 JSON（包括核心逻辑、财务预测及风险）。
   - 验证（Verification）：自动从生成的预测中抽取原文证据，并在向量库中二次反查，确保指标无幻觉。
5. **智能模型路由 (LLM Routing)**
   - 原生集成 LiteLLM，支持多厂商模型无缝切换。
   - 默认主模型：`gemini-2.5-flash`（高速推理与大上下文）。
   - 自动 Fallback：遇到 403 (未实名) 或 429 (并发限流)，自动等待并无缝回退至 `DeepSeek-R1-0528-Qwen3-8B`。

## 🛠️ 技术栈 (Tech Stack)

- **框架**: FastAPI, LangGraph, LangChain Core
- **检索**: OpenSearch 2.x (Bonsai Cloud), BGE-M3 Embeddings
- **解析**: MinerU, PyMuPDF
- **大模型**: Google Gemini 2.5 Flash, DeepSeek-R1, Qwen
- **并发**: Python `concurrent.futures`, `asyncio`

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
本项目使用 Python 3.12 虚拟环境：
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置环境变量
在项目根目录创建 `.env` 文件并填入您的 Key：
```env
# 解析器配置
PARSER_TYPE=mineru
MINERU_API_KEY=your_mineru_api_token

# RAG 向量数据库 (支持 ES 8.x 或 OpenSearch 2.x)
ELASTICSEARCH_URL=https://username:password@your-cluster.us-east-1.bonsaisearch.net
ES_INDEX_NAME=financial_reports_v2

# LLM 路由配置
LLM_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=AIzaSy...your_gemini_key

# 降级兜底模型 (可选)
FALLBACK_MODEL=openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B
OPENAI_API_KEY=sk-your_siliconflow_key
OPENAI_API_BASE=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=BAAI/bge-m3
```

### 3. 启动服务
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

## 📡 API 接口 (Usage)

### `POST /upload`
上传 PDF 金融研报并获取结构化分析结果。

**Request:**
- `Content-Type: multipart/form-data`
- `file`: 您的 PDF 文件 (如 `report.pdf`)

**Response (JSON):**
```json
{
  "data": {
    "title": "某科技公司 2024 深度研究报告",
    "core_logic": "该公司在国产 GPU 领域拥有极高的技术壁垒...",
    "revenue_forecasts": [
      {
        "year": 2024,
        "revenue_estimate": 12000000000,
        "evidence": {
          "text": "预计 2024 年营业收入将达到 120 亿元...",
          "page_number": 1
        }
      }
    ],
    "risk_warnings": "宏观经济下行风险、行业竞争加剧..."
  },
  "verification_status": "verified",
  "reasoning": "证据文本在第 1 页中被成功核实。"
}
```

## 🏗️ 架构演进与维护记录
- **2026-04-08**: 将 RAG 引擎从 FAISS 全面迁移至 **OpenSearch**，引入 Nested Mapping 与 RRF 混合检索；实现 `upload/url` 云端签名上传流，解决 API 413 限制；引入并发提问增强与 LLM Rerank 机制。模型切换为 `gemini-2.5-flash` 并强化了自动重试容错。
- **2026-04-03**: 完成初版 LlamaParse 集成与基本 LangGraph 框架构建。
