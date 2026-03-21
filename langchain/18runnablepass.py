from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document

model = ChatTongyi(model="qwen3-max")
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "以我提供的资料来回答用户的问题，参考资料{content}"),
        ("user", "用户提问：{input}"),
    ]
)

vector_store = InMemoryVectorStore(
    embedding=DashScopeEmbeddings(model="text-embedding-v4")
)

vector_store.add_texts(["减肥要少吃饭", "跑步很好", "减少油脂摄入控制卡路里"])
# 将三个texts作为文本转换为向量并存储到vector_store
input_text = "如何减肥？"


def format_func(docs: list[Document]):
    if not docs:
        return "无参考资料"
    format_str = "["
    for doc in docs:
        format_str += doc.page_content
    format_str += "]"
    return format_str


# 正文开始
retriever = vector_store.as_retriever(
    search_kwargs={"k": 2}
)  # retriever = 向量库的检索结果，k=2


def printprompt(prompt):
    print(prompt.to_string())
    return prompt


chain = (
    {"input": RunnablePassthrough(), "content": retriever | format_func}
    | prompt
    | printprompt
    | model
    | StrOutputParser()
)

res = chain.invoke(input_text)
print(res)
