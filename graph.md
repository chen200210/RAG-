graph TD
    %% 定义样式
    classDef storage fill:#f9f,stroke:#333,stroke-width:2px;
    classDef llm fill:#bbf,stroke:#333,stroke-width:2px;
    classDef process fill:#dfd,stroke:#333,stroke-width:1px;
    classDef optimization fill:#f96,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5;

    %% --- 1. 数据入库流程 ---
    subgraph Ingestion_Platform ["管理端：数据入库与向量化"]
        A["用户上传 .txt 文档"] --> B("计算 MD5 哈希值")
        B --> C{MD5 是否存在?}
        
        C -->|是| D["🌟 命中缓存：跳过向量化"]
        C -->|否| E["读取文件内容"]
        
        E --> F("RecursiveCharacterTextSplitter")
        F --> G("生成 Chunk List")
        
        G --> H["Embedding 模型 (v3-1536维)"]
        H --> I("生成向量列表")
        
        I --> J[("(ChromaDB 向量库)")]:::storage
    end

    %% --- 2. RAG 智能问答流程 ---
    subgraph QA_Platform ["用户端：RAG 智能问答 (LCEL)"]
        K["用户输入问题 prompt"] --> L("RagService.ask")
        
        %% 核心逻辑：LCEL 链式调用
        subgraph LCEL_Chain ["🌟 LCEL 声明式链式调用"]
            L --> M("RunnablePassthrough.assign")
            
            subgraph Retrieval_Flow ["检索流"]
                M --> N("1.提取问题: x['question']")
                N --> O["VectorStoreRetriever.invoke"]
                O -.->|查询| J
                O --> P("2.获取 Docs 文档片段")
                P --> Q("3.格式化: format_docs")
            end
            
            subgraph History_Flow ["🌟 历史流"]
                M --> R("4.加载 Session ID")
                R -.-> S[("(🌟 JSON 历史文件)")]:::storage
                S --> T["5.注入历史: MessagesPlaceholder"]
            end
            
            Q & T & N --> U["6.组合 Prompt 模板"]
            U --> V["7.调用模型: Qwen-Turbo"]:::llm
            V --> W("8.生成 AIMessage 回答")
        end
        
        %% 后处理与 UX
        W --> X{res 是否为字典?}
        X -->|是| Y("提取 answer & context")
        
        Y --> Z["🌟 UI 渲染: 折叠面板查看原文"]
        Y --> AA["🌟 异步更新 JSON 历史记录"]
    end

    %% 应用样式
    class J,S storage;
    class V llm;
    class D,T,S,Z,AA optimization;