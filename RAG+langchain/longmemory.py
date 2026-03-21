import os, json
from typing import Sequence
from langchain_core.messages import (
    message_to_dict,
    messages_from_dict,
    BaseMessage,
)
from langchain_core.chat_history import BaseChatMessageHistory

# message_to_dict: 单个消息转换为字典
# messages_from_dict： [字典、字典...] -> [消息、消息...]


class FileMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id, storage_path):
        self.session_id = session_id  # 会话id
        self.storage_path = (
            storage_path  # 不同会话id的聊天记录存储文件，所在的文件夹的路径
        )
        # 完整的路径
        self.file_path = os.path.join(self.storage_path, f"{self.session_id}.json")

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def add_message(self, message: Sequence[BaseMessage]) -> None:
        all_messages = self.messages
        all_messages.append(message)

        # 类对象存入文件是二进制的，因此可以把对象转为字典，把字典存成json写入文件，方便llm调取
        # new_messages=[]
        # for message in all_messages:
        #     d = message_to_dict(new_messages)
        #     new_messages.append(d)

        new_messages = [message_to_dict(message) for message in all_messages]

        # write in file
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(new_messages, f)

    @property
    def messages(self) -> list[BaseMessage]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                messages_data = json.load(f)
                return messages_from_dict(messages_data)
        except FileNotFoundError:
            return []

    def clear(self) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([], f)


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


def get_history(session_id):
    return FileMessageHistory(session_id, "./chat_history")


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
