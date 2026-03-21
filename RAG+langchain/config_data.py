from pathlib import Path

from langchain_community.embeddings import DashScopeEmbeddings

_PROJECT_DIR = Path(__file__).resolve().parents[1]

vector_db_path = str(_PROJECT_DIR / "chroma_db")
upload_dir = str(_PROJECT_DIR / "data" / "knowledge_base")
md5_path = str(_PROJECT_DIR / "md5.text")
collection_name = "rag"
embedding_function=DashScopeEmbeddings(model="text-embedding-v1")
chat_model = "qwen-plus"
persist_directory = str(_PROJECT_DIR / "chroma_db")
chunk_size = 1000
chunk_overlap = 100 
separators=["\n\n", "\n", " ","!","?",".",",","，","。","!","？"]
max_split_char_num = 1000
similarity_threshold = 2

system_prompt_template = """
# 角色
你是一个极其严谨的文档查询助手。

# 任务
请根据提供的【已知信息】回答用户的【问题】。

# 已知信息 (Context):
{context}

# 引用规范（核心要求）：
1. 你的回答必须每一句都有据可查。
2. 在回答涉及具体事实的句子末尾，必须标注其来源。
3. 标注格式为：`[来源: 文件名-片段ID]`。
4. 如果【已知信息】中没有答案，请直接回答“知识库中未记载相关内容”，严禁发挥。

# 示例：
问：公司的公积金比例是多少？
答：根据《员工福利手册》规定，公司公积金缴纳比例为12% [来源: 福利手册.txt-3]。
"""

session_config = {
    "session_id": "rag_session",
    "user_id": "rag_user",
    "assistant_id": "rag_assistant",
}
