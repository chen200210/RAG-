from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models.tongyi import ChatTongyi

model = ChatTongyi(model="qwen3-max", api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef")

chat_prompt_template = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一个边塞诗人"),
        MessagesPlaceholder("history"),
        ("human", "请再来一首诗"),
    ]
)


history_data = [
    ("human", "写一首诗"),
    ("ai", "窗前明月光"),
    ("human", "再来一个"),
    ("ai", "疑是地上霜"),
]

chain = chat_prompt_template | model

# res = chain.invoke({"history": history_data})

for chunk in chain.stream({"history": history_data}):
    print(chunk.content, end="", flush=True)
