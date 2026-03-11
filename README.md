# Report Analysis AI 结构化提取引擎

基于 FastAPI + LangGraph + LlamaParse + LiteLLM 构建的工业级金融研报解析引擎。

## 核心特性
- **Agent 工作流**: 使用 LangGraph 构建提取-自检-修正工作流。
- **高精度解析**: 集成 LlamaParse 深度处理 PDF 复杂表格。
- **证据溯源**: 强制提取结果关联原文证据链及页码。
- **统一模型管理**: 通过 LiteLLM 支持多种大模型。

## 快速开始

1. **环境安装**:
   ```bash
   pip install -r requirements.txt
   ```

2. **配置环境变量**:
   修改 `.env` 文件，填入相关的 API Key。

3. **启动服务**:
   ```bash
   python main.py
   ```

4. **接口使用**:
   - `POST /upload`: 上传 PDF 文件，返回结构化 JSON。

## 如何扩展提取字段

只需要修改 `schemas/extraction.py` 中的 `ResearchReport` Pydantic 模型。
LLM 会根据模型定义的 `description` 自动学习提取新字段。

例如，增加“所属行业”：
```python
class ResearchReport(BaseModel):
    ...
    sector: str = Field(..., description="The industry sector the company belongs to.")
```
