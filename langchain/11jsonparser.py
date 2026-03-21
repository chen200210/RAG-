from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.chat_models.tongyi import ChatTongyi

model = ChatTongyi(model="qwen3-max", api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef")
strparser = StrOutputParser()
jsonparser = JsonOutputParser()

prompt1 = PromptTemplate.from_template(
    "我邻居姓{lastname}，生了个{gender}，帮我起一个名字，别说废话，并封装成json格式，key=name，value=你起的名字。必须严格遵守要求"
)

prompt2 = PromptTemplate.from_template("姓名：{name}，帮我解析含义")

chain = prompt1 | model | jsonparser | prompt2 | model | strparser


for chunk in chain.stream({"lastname": "张", "gender": "女儿"}):
    print(chunk, end="", flush=True)
