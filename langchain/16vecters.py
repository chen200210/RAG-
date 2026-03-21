from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.document_loaders import CSVLoader

from langchain_chroma import Chroma

vector_store = Chroma(
    collection_name="test_name",
    embedding_function=DashScopeEmbeddings(),
    persist_directory="./data/chroma_db",  # 指定存放data的文件夹
)
# vector_store = InMemoryVectorStore(embedding=DashScopeEmbeddings())  # embedding模型是

loader = CSVLoader(
    file_path="./data/info.csv", encoding="utf-8", source_column="source"
)

documents = loader.load()


# 向量的crud
vector_store.add_documents(
    documents=documents,  # 通过add_documents新增documents成为要变成向量存储的文档
    ids=["id" + str(i) for i in range(1, len(documents) + 1)],
)

# delete
vector_store.delete(["id1", "id2"])

# query
result = vector_store.similarity_search(query="is pg good?", k=3)
print(result)


from langchain_chroma import Chroma

vector_chroma = Chroma(
    collection_name="test_name",
    embedding_function=DashScopeEmbeddings(),
    persist_directory="./data/chroma_db",  # 指定存放data的文件夹
)
