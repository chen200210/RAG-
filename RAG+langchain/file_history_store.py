import os, json
from typing import Sequence
from langchain_core.messages import (
    message_to_dict,
    messages_from_dict,
    BaseMessage,
)
from langchain_core.chat_history import BaseChatMessageHistory


def get_history(session_id):
    return FileMessageHistory(session_id, "./chat_history")


class FileMessageHistory(BaseChatMessageHistory):
    def __init__(self, session_id, storage_path):
        self.session_id = session_id  # 会话id
        self.storage_path = (
            storage_path  # 不同会话id的聊天记录存储文件，所在的文件夹的路径
        )
        # 完整的路径
        self.file_path = os.path.join(self.storage_path, f"{self.session_id}.json")

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

    def add_message(self, message: BaseMessage) -> None:
        """
        message: 这是系统传入的“当前这一条”消息对象
        """
        # 1. 先调用你类里的 messages 属性，获取之前所有的历史记录（列表）
        all_messages = self.messages 
        
        # 2. 把当前这一条新消息存进列表
        all_messages.append(message)

        # 3. [关键修复] 将列表里的每一个消息对象转换成字典
        # 使用 m 代替 message 避免和参数名冲突
        new_messages_data = [message_to_dict(m) for m in all_messages]

        # 4. 写入文件
        with open(self.file_path, "w", encoding="utf-8") as f:
            # ensure_ascii=False 是为了让中文不乱码
            # indent=2 是为了让生成的 JSON 文件排版漂亮，方便你手动打开看
            json.dump(new_messages_data, f, ensure_ascii=False, indent=2)

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