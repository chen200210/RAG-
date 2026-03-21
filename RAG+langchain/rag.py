from langchain_core.runnables import RunnableLambda
import config_data as config
from vector_stores import VectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.prompts import MessagesPlaceholder
from file_history_store import get_history
from langchain_community.document_compressors import DashScopeRerank


class RagService(object):

    def __init__(self):
        self.vector_store = VectorStore(config.embedding_function)
        self.llm = ChatTongyi(model=config.chat_model, temperature=0.1)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", config.system_prompt_template),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ])
        # 🌟 初始化时就准备好 chain
        self.chain = self.get_chain()

    def ask(self, question: str, config_dict: dict):
        # 1. 手动检索一次文档（为了拿给前端做悬停）
        retriever = self.vector_store.get_retriever()
        docs = retriever.invoke(question)
        
        # 2. 调用原有的 chain
        response = self.chain.invoke(
            {"question": question},
            config={"configurable": {"session_id": config_dict["session_id"]}}
        )
        
        # 3. 返回包含原文的字典
        return {"answer": response.content, "context": docs}
    


    def get_chain(self):
        retriever = self.vector_store.get_retriever()

        def format_for_retriever(value:dict)->str:
            return value["input"]
        def format_for_prompt_template(value:dict)->dict:
            new_value = {}
            new_value["history"] = value["input"]["history"]
            new_value["question"] = value["input"]["question"]
            new_value["context"] = value["context"]
            return new_value
        
        def format_docs(docs):
            if not docs:
                return "没有找到相关参考内容。"   
            return "\n\n".join(doc.page_content for doc in docs)

        # 构建基础 RAG 链
        # 这里的 input 包含 question 和 history (由 RunnableWithMessageHistory 自动注入)
        chain = (
            RunnablePassthrough.assign(
                # 从输入中提取 question，传给检索器，再格式化
                context=lambda x: format_docs(retriever.invoke(x["question"]))  
            )
            | self.prompt  # 此时字典包含 context, history, question
            | self.llm
        )

        # 包装历史记录
        # 注意：history_messages_key 必须对应 Prompt 里的 MessagesPlaceholder 变量名
        full_chain = RunnableWithMessageHistory(
            chain,
            get_history,
            input_messages_key="question",
            history_messages_key="history",
        )
        return full_chain
    
if __name__ == "__main__":
    rag_service = RagService()
    chain = rag_service.get_chain()
