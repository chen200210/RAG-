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
        {"role": "system", "content": "你是一个回答简洁的助理"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "小红有两只狗"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "小鸣有三只猪"},
        {"role": "assistant", "content": "ok"},
        {"role": "user", "content": "总共有几个宠物"},
    ],
    stream=True,
)

# 获取结果
# print(response.choices[0].message.content)
for chunk in response:
    print(chunk.choices[0].delta.content, end=" ", flush=True)
