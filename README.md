# Report Analysis AI 结构化提取引擎

基于 FastAPI + LangGraph + MinerU/LlamaParse + LiteLLM 构建的工业级金融研报解析引擎。

## 核心特性
- **Agent 工作流**: 使用 LangGraph 构建提取-自检-修正工作流。
- **高精度解析**: 
  - 支持 **MinerU (Magic-PDF)** 进行本地离线高精度解析（推荐用于内网环境）。
  - 兼容 **LlamaParse** 云端解析。
- **证据溯源**: 强制提取结果关联原文证据链及页码。
- **统一模型管理**: 通过 LiteLLM 支持多种大模型（如 DeepSeek, Qwen）。

## 快速开始

1. **环境准备**:
   项目使用虚拟环境管理依赖，确保本地 Python 环境干净。
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # Linux/macOS
   pip install -r requirements.txt
   ```

2. **配置环境变量**:
   修改 `.env` 文件：
   - `PARSER_TYPE`: 设置为 `mineru` (本地) 或 `llamaparse` (云端)。
   - `LLM_MODEL`: 主模型名称。
   - `FALLBACK_MODEL`: 备用模型名称。
   - 填入相应的 API Key。

3. **启动服务**:
   ```bash
   python main.py
   ```

4. **接口使用**:
   - `POST /upload`: 上传 PDF 文件，返回结构化 JSON。

## 测试与验证

项目包含自动化测试脚本 `test_api.py`，用于验证解析引擎的端到端流程：

1. **本地启动服务**:
   ```bash
   python main.py
   ```

2. **运行测试脚本**:
   ```bash
   python test_api.py
   ```
   该脚本会自动读取 `test_report.pdf` 并请求本地 API，输出详细的结构化 JSON 结果及证据溯源信息。

## 维护记录
- **2026-03-11**: 
  - 优化 `.gitignore`，移除追踪产生的 `server.log`。
  - 新增 `test_api.py` 方便快速验证解析精度。
  - 完成 A 股 2025 策略报告的结构化提取测试，证据溯源功能验证通过。

## 如何扩展提取字段

只需要修改 `schemas/extraction.py` 中的 `ResearchReport` Pydantic 模型。
LLM 会根据模型定义的 `description` 自动学习提取新字段。
