import config_data as config
from typing import List, Optional, Tuple, Dict, Any, Iterator

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory
from file_history_store import get_history
import os
from trace_manager import get_trace_manager, trace_step
import re

MAX_RETRIES = 3

class RagService(object):

    def __init__(self):
        # 🌟 修复：将导入放在方法内部，确保 VectorStore 已被 Python 加载
        from vector_stores import VectorStore 
        
        self.vector_store = VectorStore(config.embedding_function)
        self.llm = ChatTongyi(model=config.chat_model, temperature=0.1)
        self.control_llm = ChatTongyi(model=config.chat_model, temperature=0.0)
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

    def ask(self, question: str, config_dict: dict, use_rerank: bool = False) -> Iterator[Dict[str, Any]]:
        # 路由判定：为简单问题走“快速通道”
        route = self._route_query(question)
        fast_path = bool(route.get("fast_path"))
        reason = route.get("reason", "")
        retries_cap = 1 if fast_path else MAX_RETRIES
        effective_use_rerank = False if fast_path else use_rerank

        retrieve_k = 20 if effective_use_rerank else 8
        vector_retriever = self.vector_store.get_retriever(search_kwargs={"k": retrieve_k})
        self._ensure_bm25_ready()

        original_question = question
        current_query = question
        attempt = 0
        passed = False
        last_docs: List[Document] = []
        best_docs: List[Document] = []
        all_seen: Dict[Tuple[str, Any, str], Document] = {}
        tm = get_trace_manager()
        trace_id = tm.start_trace(original_question, {"use_rerank": use_rerank})

        # 状态提示当前路径
        if fast_path:
            yield {"type": "status", "message": f"进入快速路径（不精排、最多1轮）：{reason}"}
        else:
            yield {"type": "status", "message": "进入深度分析路径（Hybrid + Rerank + 反思循环）"}

        while attempt < retries_cap:
            yield {"type": "status", "message": f"正在检索候选片段（第 {attempt + 1}/{MAX_RETRIES} 轮）..."}
            yield {"type": "status", "message": f"检索查询: {current_query}"}
            self._current_round = attempt + 1

            initial_docs = self._hybrid_retrieve(current_query, vector_retriever, retrieve_k) or []

            if not initial_docs:
                vector_empty = False
                try:
                    vector_empty = self.vector_store.vector_db._collection.count() == 0
                except Exception:
                    vector_empty = False

                # 仅在第一轮且库为空时才允许“索引自救”
                if attempt == 0 and vector_empty and (not self._auto_index_attempted):
                    self._auto_index_attempted = True
                    yield {"type": "status", "message": "检测到检索结果为空，尝试自动同步本地知识库..."}
                    self._try_auto_index()
                    self._bm25_retriever = None
                    self._ensure_bm25_ready()
                    initial_docs = self._hybrid_retrieve(current_query, vector_retriever, retrieve_k) or []

            initial_docs = initial_docs[:retrieve_k]
            rerank_input = initial_docs
            final_docs = rerank_input[:3]

            if effective_use_rerank and rerank_input:
                yield {"type": "status", "message": f"正在对 {len(rerank_input)} 个片段进行精排..."}
                try:
                    final_docs = self._rerank(rerank_input, original_question, 3) or []
                except Exception:
                    final_docs = rerank_input[:3]

            for idx, doc in enumerate(final_docs):
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
                meta["round"] = attempt + 1
                meta["retrieval_query"] = current_query
                try:
                    doc.metadata = meta
                except Exception:
                    pass
                try:
                    setattr(doc, "relevance_score", score)
                except Exception:
                    pass

                key = (
                    str(meta.get("source", "")),
                    meta.get("chunk_id"),
                    (getattr(doc, "page_content", "") or "")[:80],
                )
                all_seen[key] = doc

            if effective_use_rerank and final_docs:
                try:
                    final_docs = sorted(
                        final_docs,
                        key=lambda d: (getattr(d, "metadata", {}) or {}).get("relevance_score", float("-inf")),
                        reverse=True,
                    )
                except Exception:
                    pass

            last_docs = final_docs
            if not best_docs and last_docs:
                best_docs = last_docs

            # 上下文精简：保留 Top-3（优先用 relevance_score，否则关键词重合度）
            compact_docs = self._select_top_docs(original_question, last_docs, top_n=3)
            formatted_context = self.format_docs(compact_docs)
            yield {"type": "status", "message": "正在评估检索质量..."}
            grade_res = self._grade_context(original_question, formatted_context)
            verdict = (grade_res or {}).get("verdict", "").upper()
            passed = verdict == "YES"
            if passed:
                yield {"type": "status", "message": "检索质量评估: YES，开始生成回答..."}
                break

            yield {"type": "status", "message": "检索质量评估: NO"}
            attempt += 1
            if attempt >= retries_cap:
                break

            yield {"type": "status", "message": f"尝试优化搜索词重试第 {attempt + 1}/{MAX_RETRIES} 次..."}
            current_query = self._rewrite_question(original_question, current_query, formatted_context)
            if not current_query:
                current_query = original_question

        final_for_llm = last_docs or best_docs
        compact_docs = self._select_top_docs(original_question, final_for_llm, top_n=3)
        formatted_context = self.format_docs(compact_docs)

        response = self._generate_answer(original_question, formatted_context, config_dict)
        answer_text = getattr(response, "content", None)
        if answer_text is None and isinstance(response, dict):
            answer_text = response.get("answer")
        if answer_text is None:
            answer_text = str(response)
        if not passed:
            answer_text = "基于现有知识库片段，信息可能不够完整，以下是根据相关片段整理的内容：\n\n" + answer_text

        # 简单流式：将已生成的答案分片推送到前端
        for i in range(0, len(answer_text), 60):
            yield {"type": "stream", "delta": answer_text[i:i+60]}

        aggregated_docs = list(all_seen.values()) if all_seen else (compact_docs or final_for_llm or [])

        if ("[来源" not in answer_text) and ("来源:" not in answer_text) and aggregated_docs:
            cite_lines = []
            for i, doc in enumerate(aggregated_docs):
                meta = getattr(doc, "metadata", {}) or {}
                source = meta.get("source") or "未知文件"
                chunk_id = meta.get("chunk_id")
                cite_id = f"{source}-{chunk_id}" if chunk_id is not None else f"Context-{i+1}"
                cite_lines.append(f"- [来源: {cite_id}]")
            answer_text = f"{answer_text}\n\n参考来源：\n" + "\n".join(cite_lines)

        tm.end_trace(answer_text, passed, attempt + 1)
        out_dir = os.path.join("logs", "traces")
        os.makedirs(out_dir, exist_ok=True)
        tm.dump_async(os.path.join(out_dir, f"trace_{trace_id}.json"))

        yield {
            "type": "final",
            "answer": answer_text,
            "context": aggregated_docs,
            "final_context": compact_docs,
            "passed": passed,
            "rounds": attempt + 1,
            "final_query": current_query,
        }

    def ask_sync(self, question: str, config_dict: dict, use_rerank: bool = False) -> Dict[str, Any]:
        final_event = None
        for event in self.ask(question, config_dict, use_rerank=use_rerank):
            if isinstance(event, dict) and event.get("type") == "final":
                final_event = event
        if not final_event:
            return {"answer": "知识库中未记载相关内容。", "context": []}
        return {"answer": final_event.get("answer", ""), "context": final_event.get("context", [])}

    @trace_step(
        name="Grader",
        round_from=lambda self, question, context: getattr(self, "_current_round", 1),
        input_fn=lambda self, question, context: {"question": question[:120], "context": context[:200]},
        output_fn=lambda res: {"verdict": res.get("verdict"), "score": res.get("score"), "reason": (res.get("reason") or "")[:200]},
    )
    def _grade_context(self, question: str, context: str) -> Dict[str, Any]:
        grader_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "判断【已知信息】是否包含回答【问题】所需的核心事实。只输出YES或NO。"),
                ("human", "问题：{question}\n\n已知信息：\n{context}\n\n判断："),
            ]
        )
        try:
            out = (grader_prompt | self.control_llm).invoke({"question": question, "context": context})
            text = getattr(out, "content", str(out)).strip().upper()
            verdict = "YES" if "YES" in text else "NO"
            score = 1.0 if verdict == "YES" else 0.0
            reason = ""
            usage = {}
            try:
                usage = getattr(out, "usage_metadata", None) or {}
                if not usage:
                    rm = getattr(out, "response_metadata", None) or {}
                    usage = rm.get("token_usage") or rm.get("usage") or {}
            except Exception:
                usage = {}
            return {"verdict": verdict, "score": score, "reason": reason, "usage_metadata": usage}
        except Exception:
            return {"verdict": "NO", "score": 0.0, "reason": "error"}

    @trace_step(
        name="Rewriter",
        round_from=lambda self, original_question, current_query, context: getattr(self, "_current_round", 1),
        input_fn=lambda self, original_question, current_query, context: {"original_question": original_question[:120], "current_query": current_query[:120]},
        output_fn=lambda text: {"new_query": text},
    )
    def _rewrite_question(self, original_question: str, current_query: str, context: str) -> str:
        # 从原问题提取需保留的核心词（简单分词替代）
        preserve_terms = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", original_question)[:5]
        preserve_hint = "、".join(preserve_terms)

        rewriter_prompt = ChatPromptTemplate.from_messages(
            [
                ("system",
                 "你是检索词改写器。"
                 "输出要求：只输出三行，每行是'关键词组'，用空格分隔，不要句子、不要标点，每行≤5个关键词。\n"
                 "例如：\n"
                 "老刀 送信 目的\n"
                 "幼儿园 赞助费 数额\n"
                 "秦天 委托 报酬\n"
                 "约束：必须保留这些核心实体，不得丢弃：{preserve}。如果已检索到部分信息，只补充缺失要点。"),
                ("human",
                 "原始问题：{original_question}\n"
                 "当前查询：{current_query}\n"
                 "已检索片段（摘要）：\n{context}\n"
                 "请给出三行关键词组："),
            ]
        )
        try:
            out = (rewriter_prompt | self.control_llm).invoke(
                {
                    "original_question": original_question,
                    "current_query": current_query,
                    "context": context[:300],
                    "preserve": preserve_hint,
                }
            )
            text = (getattr(out, "content", str(out)) or "").strip()
            # 只取前三行，拼成一行关键词，控制长度
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:3]
            if not lines:
                return ""
            merged = " | ".join(lines)
            return merged[:200]
        except Exception:
            return ""

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

    @trace_step(
        name="Retriever",
        round_from=lambda self, question, vector_retriever, k: getattr(self, "_current_round", 1),
        input_fn=lambda self, question, vector_retriever, k: {"query": question, "k": k},
        output_fn=lambda docs: {
            "size": len(docs or []),
            "sources": [
                (
                    (getattr(d, "metadata", {}) or {}).get("source"),
                    (getattr(d, "metadata", {}) or {}).get("chunk_id"),
                )
                for d in (docs or [])[:5]
            ],
        },
    )
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

    @trace_step(
        name="Rerank",
        round_from=lambda self, docs, question, top_n=3: getattr(self, "_current_round", 1),
        input_fn=lambda self, docs, question, top_n=3: {"docs": len(docs or []), "top_n": top_n},
        output_fn=lambda res: {
            "size": len(res or []),
            "sources": [
                (
                    (getattr(d, "metadata", {}) or {}).get("source"),
                    (getattr(d, "metadata", {}) or {}).get("chunk_id"),
                    (getattr(d, "metadata", {}) or {}).get("relevance_score"),
                )
                for d in (res or [])[:5]
            ],
        },
        token_usage_fn=lambda res: (
            (lambda total_chars: {
                "prompt_tokens": max(1, total_chars // 4),
                "completion_tokens": 0,
                "total_tokens": max(1, total_chars // 4),
                "estimated": True,
            })(sum(len(getattr(d, "page_content", "") or "") for d in (res or [])))
            if isinstance(res, list) else {}
        ),
    )
    def _rerank(self, docs: List[Document], question: str, top_n: int = 3) -> List[Document]:
        try:
            from langchain_community.document_compressors.dashscope_rerank import DashScopeRerank
            reranker = DashScopeRerank(model="rerank-v1", top_n=top_n)
            return reranker.compress_documents(docs, question) or []
        except Exception:
            return docs[:top_n]

    def _select_top_docs(self, question: str, docs: List[Document], top_n: int = 3) -> List[Document]:
        if not docs:
            return []
        # 优先用 rerank 分数
        has_score = any(((getattr(d, "metadata", {}) or {}).get("relevance_score") is not None) for d in docs)
        if has_score:
            scored = []
            for d in docs:
                s = (getattr(d, "metadata", {}) or {}).get("relevance_score")
                try:
                    scored.append((float(s) if s is not None else 0.0, d))
                except Exception:
                    scored.append((0.0, d))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [d for _, d in scored[:top_n]]
        # 否则关键词重合度 + 数字/事件词启发式
        import re as _re
        q_terms = set(_re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", question))
        number_like = _re.compile(r"\d+|一|二|三|四|五|六|七|八|九|十|百|千|万")
        ev_set = set(["原因", "目的", "结果", "时间", "地点", "死亡", "送信", "赞助费", "幼儿园"])
        scored = []
        for d in docs:
            text = (getattr(d, "page_content", "") or "")
            tokens = set(_re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]+", text))
            overlap = len(q_terms & tokens)
            bonus = 0
            if number_like.search(text):
                bonus += 1
            if ev_set & tokens:
                bonus += 1
            scored.append((overlap + bonus, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_n]]
    @trace_step(
        name="Generator",
        round_from=lambda self, question, context, config_dict: getattr(self, "_current_round", 1),
        input_fn=lambda self, question, context, config_dict: {"question": question[:120], "context": context[:200]},
        output_fn=lambda res: {
            "answer": (getattr(res, "content", None) or (res.get("answer") if isinstance(res, dict) else None)),
            "reasoning_path": (res.get("reasoning_path") if isinstance(res, dict) else None),
        },
    )
    def _generate_answer(self, question: str, context: str, config_dict: dict):
        # 注入 CoT 与常识推理许可的专用 Prompt
        gen_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "你是文学作品阅读理解助手。请先进行简洁、可检查的推理，再给出结论。\n"
                    "允许在尊重原文事实的基础上进行合理的常识性推理（例如：投毒+倒地不起→可能死亡），"
                    "但不得与原文事实矛盾。\n"
                    "输出格式严格分两段：\n"
                    "推理过程：\n"
                    "1) 发生的事件 →\n"
                    "2) 常识背景 →\n"
                    "3) 逻辑结论 →\n"
                    "最终回答：<一句话结论>\n"
                ),
                (
                    "human",
                    "已知上下文：\n{context}\n\n问题：{question}\n\n"
                    "请先写出“推理过程”，然后给出“最终回答”。",
                ),
            ]
        )
        out = (gen_prompt | self.llm).invoke(
            {"question": question, "context": context},
            config={"configurable": {"session_id": config_dict["session_id"]}},
        )
        raw = getattr(out, "content", str(out)) or ""
        reasoning_path = ""
        final_answer = raw
        try:
            # 粗略解析两段式输出
            parts = re.split(r"最终回答[:：]\s*", raw, maxsplit=1)
            if len(parts) == 2:
                reasoning_path = parts[0].strip()
                final_answer = parts[1].strip()
            else:
                # 退化：尝试截取“推理过程：”块
                m = re.search(r"(推理过程[:：][\s\S]+)", raw)
                if m:
                    reasoning_path = m.group(1).strip()
        except Exception:
            pass
        usage = {}
        try:
            usage = getattr(out, "usage_metadata", None) or {}
            if not usage:
                rm = getattr(out, "response_metadata", None) or {}
                usage = rm.get("token_usage") or rm.get("usage") or {}
        except Exception:
            usage = {}
        return {"answer": final_answer, "reasoning_path": reasoning_path, "usage_metadata": usage}

    @trace_step(
        name="Router",
        round_from=lambda self, question: 1,
        input_fn=lambda self, question: {"question": question[:120]},
        output_fn=lambda res: {"fast_path": res.get("fast_path"), "reason": res.get("reason", "")[:120]},
    )
    def _route_query(self, question: str) -> Dict[str, Any]:
        """
        轻量意图路由：简单事实/追问 → fast_path
        """
        try:
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "判断问题是否属于简单事实查询或基于已知上下文的追问。"
                               "只输出 JSON：{'fast': true/false, 'reason': '...'}。"),
                    ("human", "{q}"),
                ]
            )
            out = (prompt | self.control_llm).invoke({"q": question})
            text = getattr(out, "content", str(out)).strip()
            fast = False
            if any(kw in question for kw in ["是谁", "多少", "什么时候", "原因", "目的", "在哪", "定义", "结局"]):
                fast = True
            if len(question) <= 12:
                fast = True
            reason = "关键词命中快速通道" if fast else "需深度分析"
            return {"fast_path": fast, "reason": reason}
        except Exception:
            # 失败时默认深度路径，保证稳态
            return {"fast_path": False, "reason": "路由器异常，回退深度路径"}
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
