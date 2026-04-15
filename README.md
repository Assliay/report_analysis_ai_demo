# 金融研报分析 AI 引擎 (Financial Report Analysis AI Engine)

基于 **Agentic RAG** (检索增强生成) 与多路异步检索架构的金融长文档自动化分析系统。专为处理长达 100+ 页的金融深度研究报告设计，具备高精度的指标提取、自动化事实核对与多模型故障切换能力。

## 🎯 核心逻辑与架构 (Core Workflow)

系统采用 **LangGraph** 构建有状态的智能体分析流，核心逻辑如下：

1.  **多引擎解析 (Hybrid Parser)**:
    *   主路：使用 **MinerU** 进行智能排版解析，保留研报中的复杂表格与结构。
    *   兜底：若 MinerU 异常，自动降级至 **PyMuPDF** 提取纯文本。
2.  **Nested RAG 存储结构**:
    *   基于 **OpenSearch/Elasticsearch**。
    *   **Nested Mapping**: 将 PDF 全文与其物理切片绑定，在多用户/多并发场景下通过 `report_id` 实现物理级数据隔离。
3.  **多路异步检索 (Multi-Query Async Retrieval)**:
    *   **查询扩展**: 利用 LLM 将用户提取需求扩展为 3 个专业检索词（业务、财务、风险）。
    *   **并发检索**: 结合 **BM25 关键字**（强匹配金融术语）与 **kNN 向量**（语义匹配），全异步并发执行。
    *   **LLM Rerank**: 对检索结果进行精排，去除向量分高但逻辑不相关的噪音。
4.  **智能体迭代流 (Agentic Iteration)**:
    *   **Extraction 节点**: 提取符合 `ResearchReport` Pydantic Schema 的 JSON。
    *   **Verification 节点**: 自动从提取出的数据中抽取原文证据，在向量库中反查核实。
    *   **Self-Correction**: 若核实不通过，自动带着反馈进入下一轮迭代（上限 3 次）。
5.  **模型路由 (LLM Routing)**:
    *   原生集成 **LiteLLM**。
    *   默认主模型：`gemini-2.5-flash`。
    *   **自动 Fallback**: 遇到 403 (未实名) 或 429 (并发限流)，自动无缝降级至 `DeepSeek-R1` 系列模型。

## 🛠️ 技术栈 (Tech Stack)

*   **框架**: FastAPI, LangGraph, LangChain Core
*   **向量库**: OpenSearch 2.x / Elasticsearch 8.x
*   **Embeddings**: BGE-M3 (BAAI)
*   **LLM 驱动**: LiteLLM (支持多厂商 API 统一管理)
*   **并发控制**: `asyncio`, `concurrent.futures`

## 📡 核心 API 接口

### `POST /upload`
上传 PDF 研报，启动异步分析任务。
*   **Response**: 返回 `task_id`。

### `GET /status/{task_id}`
查询任务状态。
*   **States**: `pending`, `processing`, `completed`, `failed`。

### `WS /ws/status/{task_id}`
通过 WebSocket 实时获取分析进度推送。

## 🚀 快速开始

1. **安装依赖**:
   ```bash
   pip install -r requirements.txt
   ```
2. **配置环境**:
   在 `.env` 中配置 `ELASTICSEARCH_URL`、`MINERU_API_KEY` 及 `GEMINI_API_KEY`。
3. **启动服务**:
   ```bash
   python main.py --port 8001
   ```
