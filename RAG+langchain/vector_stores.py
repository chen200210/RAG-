from langchain_chroma import Chroma
import config_data as config

class VectorStore:
    def __init__(self, embedding_function):
        self.embedding_function = embedding_function
        self.chroma = Chroma(
            collection_name=config.collection_name,
            embedding_function=self.embedding_function,
            persist_directory=config.persist_directory
        )
    def get_retriever(self):
        return self.chroma.as_retriever(search_kwargs={"k": config.similarity_threshold})
if __name__ == "__main__":
    vector_store = VectorStore(config.embedding_function)
    retriever = vector_store.get_retriever()
    res =retriever.invoke("参考资料是1多还是-1多")
    print(res)