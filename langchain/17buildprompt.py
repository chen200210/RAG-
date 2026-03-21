from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

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
result = vector_store.similarity_search(input_text, k=2)

reference_text = "["
for doc in result:
    reference_text += doc.page_content
reference_text += "]"


def print_prompt(prompt):
    print(prompt.to_string())
    return prompt


chain = prompt | print_prompt | model | StrOutputParser()

res = chain.invoke({"input": input_text, "content": reference_text})
print(res)
