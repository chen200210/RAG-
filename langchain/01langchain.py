from langchain_community.llms.tongyi import Tongyi

model = Tongyi(model="qwen-max", api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef")


res = model.invoke(input="who are you")

print(res)
