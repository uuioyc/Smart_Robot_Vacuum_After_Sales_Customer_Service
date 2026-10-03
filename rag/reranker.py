"""
Reranker 服务：对初召回文档做 Cross-Encoder 精排
"""
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from utils.config_handler import rag_conf
from utils.log_handler import logger


class RerankerService():
    def __init__(self):
        self.model_name = rag_conf['rerank_model']
        self.rerank_model = CrossEncoder(self.model_name)
        logger.info(f"[Reranker]: {self.model_name}加载完成")
    def rerank(self, queries: list[str], docs: list[Document], top_k: int) -> list[Document]:
        if not docs:
            return []
        if not queries:
            return []
        try:
            all_pairs = []
            for doc in docs:
                for q in queries:
                    all_pairs.append([q, doc.page_content])

            scores = self.rerank_model.predict(all_pairs)

            idx = 0
            for doc in docs:
                doc_scores = scores[idx: idx + len(queries)]
                doc.metadata["rerank_score"] = float(max(doc_scores))
                idx += len(queries)
            sorted_docs = sorted(docs, key = lambda d : d.metadata['rerank_score'], reverse=True)
            return sorted_docs[:top_k]
        except Exception as e:
            logger.error(f"[Reranker] Rerank失败，降级为原顺序截断 ：{str(e)}")
            return docs[:top_k]