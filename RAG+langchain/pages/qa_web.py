import re
import streamlit as st
from rag import RagService
import time

# --- 1. 基础配置 ---
st.set_page_config(page_title="RAG 问答 Bot", page_icon="🤖")
st.title("🤖 知识库智能问答")
st.caption("基于上传的文档提供精准回答")

# --- 2. 初始化 Service ---
# 哪怕在不同文件，只要类定义一样，指向的数据库路径一致即可
if "rag_service" not in st.session_state:
    with st.spinner("正在加载知识库..."):
        st.session_state.rag_service = RagService()

# --- 3. 初始化展示用的消息列表 ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "你好，我是 RAG 问答 bot，有什么我可以帮助你的吗？"}
    ]

# --- 4. 渲染历史消息 (让对话流在页面刷新时不消失) ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        # 🌟 修复：针对 AI 的回答，使用 st.write 以支持 HTML 悬停效果
        if message["role"] == "assistant":
            # 即使历史里存的是普通文本，这里用 st.write 也是安全的
            st.write(message["content"], unsafe_allow_html=True)
        else:
            # 用户输入通常不包含 HTML，继续用 markdown
            st.markdown(message["content"])
# --- 5. 配置会话 ID (对接 FileMessageHistory) ---
session_config = {
    "session_id": "rag_user_001", # 这里可以自定义，对应你的 json 文件名
}
# --- 6. 聊天输入与逻辑 ---
if prompt := st.chat_input("请输入您的问题："):
    # 1. 展示用户输入
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. AI 响应
    with st.chat_message("assistant"):
        with st.spinner("查阅文档并思考中..."):
            res = st.session_state.rag_service.ask(prompt, session_config)
            
            if isinstance(res, dict):
                full_answer = res.get("answer", "")
                source_docs = res.get("context", [])
            else:
                full_answer = str(res)
                source_docs = []

            # --- 核心改进：直接显示回答 ---
            st.markdown(full_answer)

            # --- 核心改进：在下方列出引用的原文 ---
            if source_docs:
                with st.expander("查看参考原文"):
                    # 遍历所有找到的 context，按 1, 2, 3 编号列出
                    for i, doc in enumerate(source_docs):
                        st.info(f"**Context-{i+1}** 来自 《{doc.metadata.get('source', '未知文档')}》:")
                        st.caption(doc.page_content)
            
            # 存入 session 的内容，我们把回答和原文拼接在一起，保证刷新也能看到
            history_content = full_answer
            if source_docs:
                history_content += "\n\n---\n**参考原文：**\n" + "\n".join([f"Context-{i+1}: {doc.page_content[:200]}..." for i, doc in enumerate(source_docs)])
            
            st.session_state.messages.append({"role": "assistant", "content": history_content})