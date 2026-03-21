# 🤖 基于 LangChain & Streamlit 的本地 RAG 问答助手

本项目是一个完整的 **RAG (Retrieval-Augmented Generation)** 问答系统，支持大文件上传、向量化处理、多轮对话持久化以及引用原文溯源功能。

---

## 🌟 项目亮点

* **本地知识库**：支持上传 `.txt` 文档，通过 `ChromaDB` 实现本地向量存储。
* **多轮对话记忆**：自定义 `FileMessageHistory` 类，将聊天记录持久化为 JSON 文件。
* **智能引用溯源**：AI 回答中自动标注来源，并可通过 **折叠面板 (Expander)** 实时查看参考原文。
* **多页面架构**：管理端（文件上传/向量同步）与用户端（智能问答）逻辑解耦。

---

## 📁 目录结构

```plaintext
.
├── app_file_uploader.py    # 主应用入口：文件上传与管理
├── pages/
│   └── qa_web.py           # 子页面：RAG 智能问答界面
├── rag.py                  # 核心业务逻辑：封装 RAG Chain
├── knowledge.py            # 向量化同步服务
├── vector_stores.py        # 向量数据库操作封装
├── file_history_store.py   # 自定义对话历史持久化逻辑
├── config_data.py          # 配置文件（模型 ID、API Key、Prompt）
├── chat_history/           # 存储用户对话的 JSON 文件
└── chroma_db/              # 本地向量数据库存储目录
```

## 🚀 快速开始

### 1. 环境准备

确保已安装 Python 3.10+ 和 uv（或 pip）。

``` bash
# 克隆项目后，安装依赖
uv pip install streamlit langchain langchain-community langchain-chroma dashscope requests
```

### 2. 配置 API Key

在 `config_data.py` 中填写你的通义千问 API Key：

``` python
dashscope_api_key = "your_api_key_here"
```

### 3. 运行项目

务必从项目根目录启动 Streamlit，以确保多页面路由和模块导入正确：

``` bash
uv run streamlit run app_file_uploader.py
```

------------------------------------------------------------------------

## 🔧 开发过程中解决的优化点 (Engineering Log)

### 1. 向量维度强制一致性

**问题：**\
切换 Embedding 模型导致数据库读取维度冲突（1024 vs 1536）。

**方案：**\
建立模型与数据库的映射校验，通过删除 `chroma_db` 文件夹并清空 `md5.txt`
实现数据重置，确保检索与存储空间一致。

------------------------------------------------------------------------

### 2. LCEL 接口标准化

**问题：**\
旧版 LangChain 方法（`get_relevant_documents`）在 Windows
环境下报属性错误。

**方案：**\
全面采用 LCEL (LangChain Expression Language)，将所有组件通过
`.invoke()` 统一调用，增强了 Chain 的稳定性。

------------------------------------------------------------------------

### 3. 异步数据流顺序重组

**问题：**\
前端渲染时，由于变量作用域和赋值顺序问题导致"看不见 Context"。

**方案：**\
重构 `qa_web.py` 的处理时序：\
检索数据 → 解析结果 → 正则处理 → UI 渲染。

------------------------------------------------------------------------

### 4. 可视化溯源交互 (UX)

**问题：**\
传统的 HTML 悬停 (Tooltip) 在复杂 Web 环境下兼容性较差。

**方案：**\
引入 Streamlit 原生组件 `st.expander` 展示参考原文。这种方式不仅避开了
HTML 渲染坑点，还支持大段文本阅读，显著提升了 RAG 的
**Fact-checking（事实核查）** 效率。

------------------------------------------------------------------------

## 📝 待办事项 (Future Work)

-   [ ] 增加多文档并发检索优化\
-   [ ] 引入 Rerank 重新排序模型提升精度\
-   [ ] 支持 PDF 和 Markdown 格式解析\
-   [ ] 增加模型切换功能（如切换至 OpenAI 等）
