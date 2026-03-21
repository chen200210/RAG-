import config_data as config
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from file_history_store import get_history

class RagService(object):

    def __init__(self):
        # 🌟 修复：将导入放在方法内部，确保 VectorStore 已被 Python 加载
        from vector_stores import VectorStore 
        
        self.vector_store = VectorStore(config.embedding_function)
        self.llm = ChatTongyi(model=config.chat_model, temperature=0.1)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", config.system_prompt_template),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])
        
        # 初始化链
        self.chain = self.get_chain()

    # 🌟 修复：确保 format_docs 带有 self 参数，且定义在类级别
    def format_docs(self, docs):
        if not docs:
            return "没有找到相关参考内容。"   
        formatted = []
        for i, doc in enumerate(docs):
            meta = getattr(doc, "metadata", {}) or {}
            source = meta.get("source") or "未知文件"
            chunk_id = meta.get("chunk_id")
            cite_id = f"{source}-{chunk_id}" if chunk_id is not None else f"Context-{i+1}"
            formatted.append(f"[{cite_id}]\n{getattr(doc, 'page_content', '')}")
        return "\n\n".join(formatted)

    def ask(self, question: str, config_dict: dict, use_rerank: bool = False):
        # 1. 决定检索数量
        k_value = 10 if use_rerank else 3
        retriever = self.vector_store.get_retriever(search_kwargs={"k": k_value})
        
        # 🌟 关键修复：先拿到初始文档并赋值给 final_docs
        initial_docs = retriever.invoke(question)
        final_docs = initial_docs  # 默认情况下，最终文档就是初始文档
        
        # 2. Rerank 逻辑
        if use_rerank:
            from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
            reranker = DashScopeRerank(model="rerank-v1", top_n=3)
            # 如果走了这一步，final_docs 会被更新为精排后的版本
            final_docs = reranker.compress_documents(initial_docs, question)
            
        # 3. 运行 Chain (现在不论是否 Rerank，final_docs 都有值了)
        formatted_context = self.format_docs(final_docs)
        
        response = self.chain.invoke(
            {"question": question, "context": formatted_context},
            config={"configurable": {"session_id": config_dict["session_id"]}}
        )

        return {
            "answer": response.content, 
            "context": final_docs 
        }

    def get_chain(self):
        # 这里的 chain 不再需要 RunnablePassthrough.assign(context=...)
        # 因为我们在 ask 方法里已经把 context 算好传进来了
        chain = (
            self.prompt 
            | self.llm
        )

        full_chain = RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="question",
            history_messages_key="history",
        )
        return full_chain
