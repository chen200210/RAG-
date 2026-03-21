from langchain_chroma import Chroma
import config_data as config

class VectorStore:
    def __init__(self, embedding_function):
        self.vector_db = Chroma(
            collection_name=config.collection_name,
            persist_directory=config.persist_directory,
            embedding_function=embedding_function
        )

    def get_retriever(self, **kwargs):
        # 这里必须指向上面 __init__ 里定义的那个变量
        return self.vector_db.as_retriever(**kwargs)
if __name__ == "__main__":
    vector_store = VectorStore(config.embedding_function)
    retriever = vector_store.get_retriever()
    res =retriever.invoke("参考资料是1多还是-1多")
    print(res)
