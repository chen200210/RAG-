from langchain_core.prompts import PromptTemplate
from langchain_community.llms.tongyi import Tongyi


prompt_template = PromptTemplate.from_template(
    "我的邻居姓{lastname}，生了个{gender}，帮我起三个名字，简单回答。"
)

prompt_test = prompt_template.format(lastname="张", gender="女儿")

model = Tongyi(model="qwen-max", api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef")
res = model.invoke(input=prompt_test)
print(res)
