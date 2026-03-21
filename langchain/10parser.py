from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import AIMessage

model = ChatTongyi(model="qwen3-max", api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef")

prompt = PromptTemplate.from_template(
    "我邻居姓{lastname}，生了个{gender}，帮我起名，别说废话"
)

parser = StrOutputParser()

chain = prompt | model | parser | model

res: AIMessage = chain.invoke({"lastname": "张", "gender": "女儿"})

print(res.content)
