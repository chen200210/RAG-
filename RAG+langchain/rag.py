import config_data as config
from typing import List, Optional, Tuple, Dict, Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from file_history_store import get_history
import os

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
        self._auto_index_attempted = False
        self._bm25_retriever = None

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
        retrieve_k = 20 if use_rerank else 8
        vector_retriever = self.vector_store.get_retriever(search_kwargs={"k": retrieve_k})
        self._ensure_bm25_ready()
        
        # 🌟 关键修复：先拿到初始文档并赋值给 final_docs
        initial_docs = self._hybrid_retrieve(question, vector_retriever, retrieve_k)
        if not initial_docs:
            vector_empty = False
            try:
                vector_empty = self.vector_store.vector_db._collection.count() == 0
            except Exception:
                vector_empty = False

            if vector_empty or (not self._auto_index_attempted):
                self._auto_index_attempted = True
                self._try_auto_index()
                self._bm25_retriever = None
                self._ensure_bm25_ready()
                initial_docs = self._hybrid_retrieve(question, vector_retriever, retrieve_k)

        initial_docs = (initial_docs or [])[:retrieve_k]
        final_docs = initial_docs[:3]
        
        # 2. Rerank 逻辑
        if use_rerank:
            from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
            reranker = DashScopeRerank(model="rerank-v1", top_n=3)
            # 如果走了这一步，final_docs 会被更新为精排后的版本
            final_docs = reranker.compress_documents(initial_docs, question)

        for doc in final_docs or []:
            meta = getattr(doc, "metadata", None) or {}
            score = getattr(doc, "relevance_score", None)
            if score is None:
                score = meta.get("relevance_score")
            if score is None:
                score = meta.get("score")
            if score is None:
                score = meta.get("relevance")
            if use_rerank:
                try:
                    score = float(score) if score is not None else None
                except Exception:
                    score = None
            else:
                score = None
            meta["relevance_score"] = score
            try:
                doc.metadata = meta
            except Exception:
                pass
            try:
                setattr(doc, "relevance_score", score)
            except Exception:
                pass

        if use_rerank and final_docs:
            try:
                final_docs = sorted(
                    final_docs,
                    key=lambda d: (
                        getattr(d, "metadata", {}) or {}
                    ).get("relevance_score", float("-inf")),
                    reverse=True,
                )
            except Exception:
                pass
            
        # 3. 运行 Chain (现在不论是否 Rerank，final_docs 都有值了)
        formatted_context = self.format_docs(final_docs)
        
        response = self.chain.invoke(
            {"question": question, "context": formatted_context},
            config={"configurable": {"session_id": config_dict["session_id"]}}
        )

        answer_text = response.content
        if ("[来源" not in answer_text) and ("来源:" not in answer_text) and final_docs:
            cite_lines = []
            for i, doc in enumerate(final_docs):
                meta = getattr(doc, "metadata", {}) or {}
                source = meta.get("source") or "未知文件"
                chunk_id = meta.get("chunk_id")
                cite_id = f"{source}-{chunk_id}" if chunk_id is not None else f"Context-{i+1}"
                cite_lines.append(f"- [来源: {cite_id}]")
            answer_text = f"{answer_text}\n\n参考来源：\n" + "\n".join(cite_lines)

        return {
            "answer": answer_text,
            "context": final_docs 
        }

    def _ensure_bm25_ready(self) -> None:
        if self._bm25_retriever is not None:
            return
        try:
            from langchain_community.retrievers import BM25Retriever
        except Exception:
            return

        if not os.path.isdir(config.upload_dir):
            return

        splitter = RecursiveCharacterTextSplitter(
            separators=config.separators,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap,
        )

        docs: List[Document] = []
        for fname in os.listdir(config.upload_dir):
            if not fname.lower().endswith(".txt"):
                continue
            file_path = os.path.join(config.upload_dir, fname)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = f.read()
            except Exception:
                try:
                    with open(file_path, "r", encoding="gbk") as f:
                        data = f.read()
                except Exception:
                    continue

            chunks = splitter.split_text(data)
            for i, text in enumerate(chunks):
                docs.append(
                    Document(
                        page_content=text,
                        metadata={"source": fname, "chunk_id": i + 1},
                    )
                )

        if not docs:
            return

        try:
            bm25 = BM25Retriever.from_documents(docs)
            self._bm25_retriever = bm25
        except Exception:
            self._bm25_retriever = None

    def _hybrid_retrieve(self, question: str, vector_retriever, k: int) -> List[Document]:
        vector_docs: List[Document] = []
        try:
            vector_docs = vector_retriever.invoke(question) or []
        except Exception:
            vector_docs = []

        bm25_docs: List[Document] = []
        if self._bm25_retriever is not None:
            try:
                self._bm25_retriever.k = k
            except Exception:
                pass
            try:
                bm25_docs = self._bm25_retriever.invoke(question) or []
            except Exception:
                bm25_docs = []

        if not bm25_docs:
            return vector_docs[:k]

        weights = {"vector": 0.6, "bm25": 0.4}
        scores: Dict[Tuple[str, Any, str], float] = {}
        by_key: Dict[Tuple[str, Any, str], Document] = {}

        def key_of(doc: Document) -> Tuple[str, Any, str]:
            meta = getattr(doc, "metadata", {}) or {}
            source = str(meta.get("source", ""))
            chunk_id = meta.get("chunk_id")
            text_prefix = (getattr(doc, "page_content", "") or "")[:80]
            return (source, chunk_id, text_prefix)

        for idx, doc in enumerate(vector_docs[:k]):
            key = key_of(doc)
            by_key[key] = doc
            scores[key] = scores.get(key, 0.0) + weights["vector"] / (idx + 1)

        for idx, doc in enumerate(bm25_docs[:k]):
            key = key_of(doc)
            by_key[key] = doc
            scores[key] = scores.get(key, 0.0) + weights["bm25"] / (idx + 1)

        merged = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [by_key[kv[0]] for kv in merged[:k]]

    def _try_auto_index(self):
        try:
            from knowledge import KnowledgeBaseService
        except Exception:
            return

        try:
            kb = KnowledgeBaseService()
        except Exception:
            return

        try:
            force_reindex = False
            try:
                force_reindex = kb.chroma._collection.count() == 0
            except Exception:
                force_reindex = False

            if not os.path.isdir(config.upload_dir):
                return
            for fname in os.listdir(config.upload_dir):
                if not fname.lower().endswith(".txt"):
                    continue
                file_path = os.path.join(config.upload_dir, fname)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = f.read()
                except Exception:
                    try:
                        with open(file_path, "r", encoding="gbk") as f:
                            data = f.read()
                    except Exception:
                        continue
                if force_reindex:
                    try:
                        kb._remove_md5_by_filename(fname)
                    except Exception:
                        pass
                kb.upload_by_str(data, fname)
        except Exception:
            return

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
