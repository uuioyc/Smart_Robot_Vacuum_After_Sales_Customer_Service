from typing import List

import jieba
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from rag.vector_store import VectorStoreService
from utils.log_handler import logger


def jieba_tokenizer(text: str) -> list[str]:
    """中文分词"""
    return list(jieba.cut(text))

"""
用 jieba 做中文分词，BM25 对中文才有效（不装 jieba 的话 BM25 会把整句当一个 token）
BM25 索引在启动时构建一次，之后查询很快
"""
class BM25RetrieverService:
    def __init__(self):
        # 从向量库拿到所有文档，构建BM25索引
        vs = VectorStoreService()
        store = vs.vector_store.get()

        documents = store.get("documents", [])
        metadatas = store.get("metadatas", [])

        if not documents:
            logger.warning("[BM25] 向量库为空，BM25无法初始化")
            self.retriever = None
            return

        docs = [
            Document(page_content=c, metadata=m)
            for c, m in zip(documents, metadatas)
        ]

        #构建BM25检索器，用jieba做分词

        self.retriever = BM25Retriever.from_documents(
            docs,
            preprocess_func=jieba_tokenizer
        )

        logger.info(f"[BM25] 索引构建完成，共{len(docs)}篇文档")

    def search(self, query: str, k: int = 20) -> list[Document]:
        if not self.retriever:
            return []
        self.retriever.k = k
        return self.retriever.invoke(query)