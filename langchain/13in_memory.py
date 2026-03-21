from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.chat_history import InMemoryChatMessageHistory

model = ChatTongyi(
    model="qwen3-max",
    api_key="sk-d7202b30f741442e9c91ef5ab39cb2ef",
    temperature=0.5,
)

prompt1 = PromptTemplate.from_template(
    "根据历史记录回答用户问题。对话历史：{history}，用户提问：{input}，请回答"
)

str_parser = StrOutputParser()

base_chain = prompt1 | model | str_parser

store = {}


def get_history(session_id):
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


# 创建一个新的chain，可以增强原先的chain：自动附加历史消息

chain = RunnableWithMessageHistory(
    base_chain, get_history, input_messages_key="input", history_messages_key="history"
)
if __name__ == "__main__":
    # 配置session id
    session_config = {
        "configurable": {"session_id": "user001"},
    }
    res = chain.invoke({"input": "小明有两个猫"}, session_config)

    print("第1次：", res)
    res = chain.invoke({"input": "小李有3个猫"}, session_config)

    print("第2次：", res)
    res = chain.invoke({"input": "总共有几个宠物"}, session_config)

    print("第3次：", res)
