import re
import streamlit as st
from rag import RagService
import time
import html

# --- 1. 基础配置 ---
st.set_page_config(page_title="RAG 问答 Bot", page_icon="🤖", layout="wide")
st.title("🤖 知识库智能问答")
st.caption("基于高级 RAG 架构（向量检索 + BGE-Rerank）提供精准回答")

st.markdown(
    """
<style>
.rag-cite {
  position: relative;
  color: #ff4b4b;
  cursor: help;
  border-bottom: 2px dotted #ff4b4b;
  font-weight: 700;
}
.rag-cite::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 0;
  top: 1.6em;
  z-index: 9999;
  max-width: 520px;
  width: max-content;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(0,0,0,0.08);
  background: rgba(255,255,255,0.98);
  color: #111827;
  box-shadow: 0 12px 30px rgba(0,0,0,0.18);
  white-space: normal;
  line-height: 1.45;
  font-weight: 400;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity 120ms ease-in-out, visibility 0ms linear 120ms;
  transition-delay: 1000ms;
}
.rag-cite:hover::after {
  opacity: 1;
  visibility: visible;
  transition-delay: 1000ms;
}
</style>
""",
    unsafe_allow_html=True,
)

# --- 2. 初始化 Service ---
if "rag_service" not in st.session_state:
    with st.spinner("正在加载知识库与模型..."):
        st.session_state.rag_service = RagService()

# --- 3. 初始化展示用的消息列表 ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好，我是 RAG 问答 bot，有什么我可以帮助你的吗？", "sources": []}
    ]

# --- 4. 配置侧边栏 ---
with st.sidebar:
    st.header("⚙️ 算法配置")
    use_rerank = st.toggle("启用 BGE-Rerank 精排", value=False)
    
    if use_rerank:
        st.success("🚀 模式：高级 RAG (k=10 + Rerank)")
    else:
        st.info("🐢 模式：基础 RAG (k=3)")
    
    st.divider()
    if st.button("清除对话历史"):
        st.session_state.messages = [
            {"role": "assistant", "content": "对话已重置，请提问。", "sources": []}
        ]
        st.rerun()

session_config = {"session_id": "rag_user_001"}

def _normalize_sources(source_docs):
    normalized = []
    for doc in (source_docs or []):
        if isinstance(doc, dict):
            metadata = doc.get("metadata", {}) or {}
            score = doc.get("relevance_score")
            if score is None:
                score = metadata.get("relevance_score")
            metadata = dict(metadata)
            metadata["relevance_score"] = score
            normalized.append({"page_content": doc.get("page_content", ""), "metadata": metadata})
        else:
            metadata = getattr(doc, "metadata", {}) or {}
            score = getattr(doc, "relevance_score", None)
            if score is None:
                score = metadata.get("relevance_score")
            metadata = dict(metadata)
            metadata["relevance_score"] = score
            normalized.append({"page_content": getattr(doc, "page_content", "") or "", "metadata": metadata})
    return normalized

def _build_citation_to_doc_map(source_docs):
    citation_map = {}
    for i, doc in enumerate(source_docs):
        meta = doc.get("metadata", {}) or {}
        source = str(meta.get("source", ""))
        chunk_id = meta.get("chunk_id")
        if source and chunk_id is not None:
            citation_map[f"{source}-{chunk_id}"] = doc
        citation_map[f"Context-{i+1}"] = doc
    return citation_map

def _enrich_answer_with_tooltips(answer: str, source_docs):
    docs = _normalize_sources(source_docs)
    citation_map = _build_citation_to_doc_map(docs)

    def repl(match: re.Match):
        cite_id = match.group(1).strip()
        doc = citation_map.get(cite_id)
        if not doc:
            return match.group(0)
        tooltip_text = (doc.get("page_content", "") or "").replace("\n", " ").strip()
        tooltip_text = tooltip_text[:800]
        tooltip_text = html.escape(tooltip_text, quote=True)
        display_id = cite_id
        if cite_id.startswith("Context-"):
            meta = doc.get("metadata", {}) or {}
            source = meta.get("source")
            chunk_id = meta.get("chunk_id")
            if source and (chunk_id is not None):
                display_id = f"{source}-{chunk_id}"

        display_id_html = html.escape(display_id, quote=True)
        return f'<span class="rag-cite" data-tooltip="{tooltip_text}">[来源: {display_id_html}]</span>'

    return re.sub(r"`?\[来源:\s*([^\]]+)\]`?", repl, answer)

# --- 5. 渲染历史消息 ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            st.markdown(message["content"], unsafe_allow_html=True)
        else:
            st.markdown(message["content"])

        if message.get("sources"):
            with st.expander("🔍 查看历史参考原文"):
                for i, doc in enumerate(_normalize_sources(message["sources"])):
                    source_name = doc["metadata"].get('source', '未知')
                    st.caption(f"**Context-{i+1}** (来源: {source_name})")
                    score = doc["metadata"].get("relevance_score")
                    if score is not None:
                        try:
                            st.markdown(f":blue[得分: {float(score):.2f}]")
                        except Exception:
                            st.markdown(":blue[得分: N/A]")
                    else:
                        st.markdown(":blue[得分: N/A]")
                    st.text(doc["page_content"])
# --- 6. 聊天输入与逻辑 ---
if prompt := st.chat_input("请输入您的问题...", key="rag_chat_input"):
    # 1. 立即展示并记录用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt, "sources": []})

    # 2. AI 响应容器
    with st.chat_message("assistant"):
        with st.spinner("查阅文档并思考中..."):
            # 调用后台
            res = st.session_state.rag_service.ask(prompt, session_config, use_rerank=use_rerank)
            
            # 确保解析不出错
            full_answer = ""
            source_docs = []
            if isinstance(res, dict):
                full_answer = res.get("answer", "")
                source_docs = res.get("context", [])
            else:
                full_answer = str(res)

            # 🌟 A. 渲染回答（把 [来源: ...] 替换成可悬浮的红色虚线引用）
            enriched_html = _enrich_answer_with_tooltips(full_answer, source_docs)
            st.markdown(enriched_html, unsafe_allow_html=True)

            # 🌟 B. 紧接着渲染原文卡片 (确保这几行在 assistant 消息框内)
            normalized_sources = _normalize_sources(source_docs)
            if normalized_sources:
                with st.expander("🔍 查看参考原文", expanded=True):
                    for i, doc in enumerate(normalized_sources):
                        src_name = doc["metadata"].get('source', '本地文档')
                        st.info(f"**Context-{i+1}** 来自 《{src_name}》:")
                        if use_rerank:
                            score = doc["metadata"].get("relevance_score")
                            if score is not None:
                                try:
                                    st.markdown(f":blue[得分: {float(score):.2f}]")
                                except Exception:
                                    st.markdown(":blue[得分: N/A]")
                            else:
                                st.markdown(":blue[得分: N/A]")
                        else:
                            st.markdown("得分: N/A")
                        st.caption(doc["page_content"])
            
            # 3. 🌟 C. 存入历史记录 (注意：要存入 sources 供刷新后渲染)
            st.session_state.messages.append({
                "role": "assistant", 
                "content": enriched_html,
                "sources": normalized_sources
            })
