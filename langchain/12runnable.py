from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models.tongyi import ChatTongyi

from langchain_core.runnables import RunnableLambda

model = ChatTongyi(
    model="qwen3-max",
    api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef",
    temperature=0.5,
)
strparser = StrOutputParser()


prompt1 = PromptTemplate.from_template(
    "我邻居姓{lastname}，生了个{gender}，帮我起3个名字，别说废话"
)

prompt2 = PromptTemplate.from_template("姓名：{name}，帮我解析含义,少说废话")

dic_func = RunnableLambda(lambda ai_msg: {"name": ai_msg.content})

chain = prompt1 | model | dic_func | prompt2 | model | strparser


for chunk in chain.stream({"lastname": "张", "gender": "女儿"}):
    print(chunk, end="", flush=True)
