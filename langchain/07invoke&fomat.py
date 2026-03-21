from langchain_core.prompts import (
    FewShotPromptTemplate,
    PromptTemplate,
    ChatPromptTemplate,
)


template = PromptTemplate.from_template("my name is {name}, and my hobby is {hobby}.")

res = template.format(name="james", hobby="basketball")

res2 = template.invoke({"name": "james", "hobby": "basketball"})

print(res)
print(res2)
