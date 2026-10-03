from abc import ABC,abstractmethod
from typing import Optional, Union

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from utils.config_handler import rag_conf
import os

api_key = os.getenv(rag_conf["api_key_env"])
if not api_key:
    raise RuntimeError(f"环境变量 {rag_conf['api_key_env']} 未设置")

class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Union[Embeddings, BaseChatModel]:
        pass

class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Union[Embeddings, BaseChatModel]:
        return ChatOpenAI(
            model=rag_conf['chat_model_name'],
            api_key=api_key,
            base_url=rag_conf['base_url']
        )

class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Union[Embeddings, BaseChatModel]:
        return OpenAIEmbeddings(
            model=rag_conf['embedding_model_name'],
            api_key=api_key,
            base_url=rag_conf['base_url'],
            check_embedding_ctx_length=False,
            chunk_size=10
        )

chat_model = ChatModelFactory().generator()
embedding_model = EmbeddingsFactory().generator()

