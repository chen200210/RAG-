from langchain_core.prompts import FewShotPromptTemplate, PromptTemplate
from langchain_community.llms.tongyi import Tongyi

example_template = PromptTemplate.from_template("单词：{word}，反义词：{antonym}")

examples_data = [{"word": "big", "antonym": "small"}, {"word": "up", "antonym": "down"}]

few_shot_template = FewShotPromptTemplate(
    example_prompt=example_template,  # 示例数据的模板
    examples=examples_data,  # 示例数据们
    prefix="根据以下示例，告知我单词的反义词是什么：",
    suffix="基于示例，告诉我{input_word}的反义词是什么",
    input_variables=["input_word"],
)
prompt_test = few_shot_template.invoke(input={"input_word": "left"}).to_string()

print(prompt_test)

model = Tongyi(model="qwen-max", api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef")

res = model.invoke(input=prompt_test)
print(res)
