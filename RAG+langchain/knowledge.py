from langchain_core.documents import Document
import datetime
import os
from datetime import datetime
from langchain_text_splitters import RecursiveCharacterTextSplitter
import hashlib
import config_data as config
from langchain_chroma import Chroma
from file_history_store import FileMessageHistory
from langchain_core.runnables import RunnableWithMessageHistory



def get_history(session_id: str):
    # 确保文件夹存在，统一管理路径
    storage_path = "./chat_history"
    return FileMessageHistory(session_id, storage_path)
class KnowledgeBaseService(object):
    def __init__(self):
        os.makedirs(config.persist_directory, exist_ok=True)
        self.chroma = Chroma(
            collection_name=config.collection_name,
            embedding_function=config.embedding_function,
            persist_directory=config.persist_directory,
        )
        self.splider = RecursiveCharacterTextSplitter(  # 文本分割器
            separators=config.separators,
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        
        # [优化点 1] 初始化一个内存集合(Set)用于缓存 MD5，查找时间复杂度为 O(1)
        self.md5_cache = {} # 注意：这里从 set 改为 dict
        self._load_md5_cache() # 实例化时一次性加载历史记录

    def _load_md5_cache(self):
        """
        [优化点 2] 启动时一次性读取文件，避免每次校验都发生磁盘 I/O
        """
        if os.path.exists(config.md5_path):
            with open(config.md5_path, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        fname, m_str = line.strip().split(":", 1)
                        self.md5_cache[fname] = m_str
        # 后续校验时直接在 dict 里查找可以减轻查找负担

    def check_md5(self, filename: str, current_md5: str) -> bool:
        """
        校验逻辑：文件名存在且 MD5 一致才跳过
        """
        return self.md5_cache.get(filename) == current_md5

    def save_md5(self, filename: str, md5_str: str):
        """
        [优化点 4] 保存时同步更新内存缓存和本地文件
        """
        self.md5_cache[filename] = md5_str
        with open(config.md5_path, "a", encoding="utf-8") as f:
            f.write(f"{filename}:{md5_str}\n")


    @staticmethod
    def get_md5_string(input_str: str, encoding="utf-8") -> str:
        """
        转换字符串为二进制bytes然后再md5 (保持原逻辑，改为静态方法)
        """
        str_bytes = input_str.encode(encoding=encoding)
        md5_obj = hashlib.md5()
        md5_obj.update(str_bytes)
        return md5_obj.hexdigest()

    def upload_by_str(self, data: str, filename: str):
        """
        完整的上传逻辑示例
        """
        chunk_salt = f"|chunk_size={config.chunk_size}|chunk_overlap={config.chunk_overlap}|separators={','.join(config.separators)}"
        current_md5 = self.get_md5_string(data + chunk_salt)
        # 传入文件名进行精准校验
        if self.check_md5(filename, current_md5):
            print(f"内容未变，跳过: {filename}")
            return None
            
        # 3. 如果没处理过，执行耗时的切分和向量化逻辑...
        print(f"开始向量化并存入数据库: {filename}")
        # 4. 切分文本
        # 注意：这里直接使用切分器，它会自动处理长度逻辑
        chunks = self.splider.split_text(data)
        # [核心修改] 构建带元数据的 Document 对象列表

        docs = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for i, text in enumerate(chunks):
            new_doc = Document(
                page_content=text,
                metadata={
                    "source": filename,      # 文件名
                    "chunk_id": i + 1,        # 片段序号
                    "created_at": now_str     # 创建时间
                }
            )
            docs.append(new_doc)
        # 5. 向量化并批量存入 Chroma,412KB 的文件通过 add_documents 一次性提交，比循环快得多
        try:
            self.chroma.add_documents(docs)
        except Exception as e:
            # 这里的报错通常是网络问题或 API Key 欠费
            print(f"向量化存储到 Chroma 时出错: {e}")
            return f"存储失败: {e}"
        
        # 4. 处理完成后，记录 MD5
        self.save_md5(filename, current_md5)
        return f"成功同步 {filename}"

    def delete_document(self, filename: str):
        """
        联动删除：物理文件 + 向量数据 + MD5记录（可选）
        """
        # 1. 从 Chroma 向量数据库中删除
        # Chroma 支持通过 metadata 筛选删除
        try:
            self.chroma.delete(where={"source": filename})
            print(f"已从 Chroma 删除文件向量: {filename}")
        except Exception as e:
            print(f"Chroma 删除失败: {e}")

        # 2. 从本地磁盘删除物理文件
        file_path = os.path.join(config.upload_dir, filename) # 确保路径正确
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"已从磁盘删除物理文件: {filename}")

        # 3. 关于 MD5 的处理（重要！）
        # 如果你不删除 md5.txt 里的记录，下次上传同名同内容文件时，程序依然会跳过。
        # 如果你想允许“删了再传”，需要重写整个 md5.txt（去掉这一行）
        self._remove_md5_by_filename(filename)


    def _remove_md5_by_filename(self, filename: str):
        """
        [补全逻辑]：只删除特定文件的 MD5 记录，允许文件删除后重新上传
        """
        # 1. 从内存字典删除
        if filename in self.md5_cache:
            del self.md5_cache[filename]
        
        # 2. 重写 md5.txt 文件（过滤掉该文件行）
        if os.path.exists(config.md5_path):
            with open(config.md5_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            with open(config.md5_path, "w", encoding="utf-8") as f:
                for line in lines:
                    # 只有不以 "文件名:" 开头的行才保留
                    if not line.startswith(f"{filename}:"):
                        f.write(line)
            print(f"✅ 已精准清理 {filename} 的 MD5 记录")
    def ask(self, question: str, session_id: str):
        # 1. 创建你的 RAG 链 (包含前面提到的历史感知逻辑)
        # ... (此处省略之前的 rag_chain 定义) ...

        # 2. 包装持久化历史记录
        with_history = RunnableWithMessageHistory(
            self.rag_chain,
            get_history, # 关键：调用你写的那个 FileMessageHistory
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

        # 3. 调用并自动保存到 JSON
        response = with_history.invoke(
            {"input": question},
            config={"configurable": {"session_id": session_id}}
        )
        return response




if __name__ == "__main__":
    # 测试代码
    os.makedirs(config.upload_dir, exist_ok=True)
    service = KnowledgeBaseService()
    
    # 模拟数据上传
    text_data_1 = "这是第一份关于LangChain的文档内容"
    text_data_2 = "这是第二份关于Agent的文档内容"
    
    service.upload_by_str(text_data_1, "doc1.txt") # 第一次上传会执行
    service.upload_by_str(text_data_1, "doc1.txt") # 第二次上传会直接被拦截跳过
    service.upload_by_str(text_data_2, "doc2.txt") # 新内容会执行
