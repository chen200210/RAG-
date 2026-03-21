from openai import OpenAI


# 获取client--openai的类对象
client = OpenAI(
    api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)


# 调用模型
response = client.chat.completions.create(
    model="qwen3-max",
    messages=[
        {"role": "system", "content": "你是一个python专家，并且不说废话"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "用python输出1-10"},
    ],
)

# 获取结果
print(response.choices[0].message.content)
