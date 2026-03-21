from datetime import time
import streamlit as st
from knowledge import KnowledgeBaseService
import os
import config_data as config

# --- 1. 页面配置 (必须是第一个 Streamlit 命令) ---
st.set_page_config(page_title="知识库管理", page_icon="📚", layout="wide")

# --- 2. 初始化服务 (确保目录存在) ---
if "service" not in st.session_state:
    with st.spinner("正在初始化服务..."):
        st.session_state["service"] = KnowledgeBaseService()

if not os.path.exists(config.upload_dir):
    os.makedirs(config.upload_dir)

# --- 3. 侧边栏：文件仓库管理 ---
with st.sidebar:
    st.title("📂 知识库文件列表")
    current_files = os.listdir(config.upload_dir)
    if not current_files:
        st.info("库中暂无文件")
    else:
        for f in current_files:
            c1, c2 = st.columns([0.7, 0.3])
            c1.caption(f"📄 {f}")
            # 使用唯一 key 防止冲突
            if c2.button("删", key=f"sidebar_del_{f}"):
                st.session_state["service"].delete_document(f)
                st.rerun()

# --- 4. 主界面：上传与同步 ---
st.title("📚 知识库更新服务")
st.markdown("---")

uploader_file = st.file_uploader("第一步：选择需要上传的 .txt 文档", type=["txt"])

if uploader_file:
    # 自动识别编码
    content_raw = uploader_file.getvalue()
    try:
        content = content_raw.decode("utf-8")
    except:
        content = content_raw.decode("gbk")

    # 布局：左边看详情，右边看预览
    col_info, col_prev = st.columns([1, 2])
    
    with col_info:
        st.subheader("📑 文件信息")
        st.write(f"**文件名:** {uploader_file.name}")
        st.write(f"**大小:** {uploader_file.size / 1024:.2f} KB")
        
        # ✅ 点击按钮才触发向量化，避免反复执行
        if st.button("🚀 开始向量化同步", use_container_width=True):
            # 1. 先把文件物理存入硬盘，这样侧边栏刷新后才能看到它
            with open(os.path.join(config.upload_dir, uploader_file.name), "w", encoding="utf-8") as f:
                f.write(content)
            with st.status("处理中...", expanded=True) as status:
                st.write("正在切分并计算向量...")
                # 调用你的 Service
                msg = st.session_state["service"].upload_by_str(content, uploader_file.name)
                # 3. 刷新页面，让侧边栏同步显示
                st.rerun()
                if msg:
                    status.update(label="✅ 同步成功", state="complete")
                    st.success(msg)
                    # 模拟延迟后刷新，让侧边栏同步更新文件列表
                    time.sleep(1)
                    st.rerun()
                else:
                    status.update(label="⚠️ 跳过", state="complete")
                    st.warning("该内容已在库中。")

    with col_prev:
        st.subheader("🔍 内容预览 (前1000字)")
        st.text_area("", value=content[:1000], height=300)