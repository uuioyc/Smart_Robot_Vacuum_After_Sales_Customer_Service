"""
rag总结服务类： 用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
"""
import os
from collections import defaultdict

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.bm25_retriever import BM25RetrieverService
from rag.fusion import rrf_fusion
from rag.query_rewriter import QueryRewriter
from rag.reranker import RerankerService
from rag.vector_store import VectorStoreService
from utils.config_handler import rag_conf
from utils.log_handler import logger
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model

class RagSummarizeService(object):
    def __init__(self):
        # 1. 先读配置（轻量、快速、易失败）
        self.enable_query_rewrite = rag_conf['enable_query_rewrite']
        self.rewrite_query_num = rag_conf['rewrite_query_num']
        self.top_k = rag_conf['final_top_k']
        self.enable_rerank = rag_conf['enable_rerank']
        self.rerank_model = rag_conf['rerank_model']
        self.min_reliable_score = rag_conf['min_reliable_score']
        self.enable_hybrid = rag_conf['enable_hybrid_search']
        self.bm25_top_k = rag_conf['bm25_top_k']
        self.rrf_k = rag_conf['rrf_k']

        # 2. 再初始化重组件
        self.vector_service = VectorStoreService()
        self.retriever = self.vector_service.get_retriever()
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

        # 3. 依赖配置的组件放最后
        self.query_writer = QueryRewriter() if self.enable_query_rewrite else None
        self.reranker = RerankerService() if self.enable_rerank else None
        self.bm25_retriever = BM25RetrieverService() if self.enable_hybrid else None
    def _init_chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    def retriever_docs(self, query: str, history: list = None) -> list[Document]:

        if history and len(history) >= 2:
            last_user_q = next(
                (m["content"] for m in reversed(history) if m["role"] == "user"),
                None
            )
            if last_user_q and len(query) < 20: #短查询，可能是追问
                query_for_rewrite = f"{last_user_q} (追问: {query})"
            else:
                query_for_rewrite = query
        else:
            query_for_rewrite = query

        queries = [query_for_rewrite]
        if self.enable_query_rewrite and self.query_writer:
            result = self.query_writer.rewrite(query_for_rewrite)
            queries = [result.standard_query] + result.sub_queries
            queries = queries[:self.rewrite_query_num]
            logger.info(f"--> 触发 Multi-Query 检索，使用的 Query 列表: {queries}")

        all_docs = []
        seen_contents = set()
        """
            fusion会把向量检索和bm25检索得到的两路结果按照得分排序返回前top_n个
            然后再rerank得到钱top_k个
            理论上有3个重写问题，每个问题两路，每路20篇，一共3 * 2 * 20 = 120篇
        """
        for q in queries:
            vec_docs = self.retriever.invoke(q)

            if self.enable_hybrid and self.bm25_retriever:
                bm25_docs = self.bm25_retriever.search(q, k=self.bm25_top_k)

                merged = rrf_fusion([vec_docs, bm25_docs], k=self.rrf_k, top_n=20)

            for doc in merged:
                if doc.page_content not in seen_contents:
                    seen_contents.add(doc.page_content)
                    all_docs.append(doc)
        logger.info(f"--> 粗召回 {len(all_docs)} 篇，进入 Rerank")
        # 诊断：打印 all_docs 的 rrf_score 分布
        rrf_scores = [doc.metadata.get("rrf_score", "N/A") for doc in all_docs]
        logger.info(f"--> all_docs 的 rrf_score 分布: {rrf_scores}")
        if self.reranker:
            final_docs = self.reranker.rerank(queries, all_docs, self.top_k)
        else:
            final_docs = all_docs[:self.top_k]
        #打印最终 Top-K
        for i, doc in enumerate(final_docs, 1):
            rerank_score = doc.metadata.get("rerank_score", "N/A")
            rrf_score = doc.metadata.get("rrf_score", "N/A")
            logger.info(f"  [Top{i}] rerank_score={rerank_score} | rrf_score = {rrf_score} ")

        return final_docs

    def rag_summarize(self, query: str) -> dict:
        context_docs = self.retriever_docs(query)

        if not context_docs:
            return {
                "answer": "抱歉，我的知识库中暂时没有相关信息，建议您联系人工客服。",
                "sources": [],
                "has_reliable_source": False
            }

        if self.reranker and self.enable_rerank:
            top1_score = context_docs[0].metadata["rerank_score"]
            if top1_score < self.min_reliable_score:
                logger.warning(f"Top1 分数 {top1_score} 低于阈值 {self.min_reliable_score}，判定为低置信度")
                return {
                    "answer": "抱歉，我未能从知识库中找到足够可靠的依据。建议您换个问法或联系人工客服。",
                    "sources": [],
                    "has_reliable_source": False
                }

        context = ""
        sources_map = defaultdict(list)
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"[参考资料{counter}]:{doc.page_content} | 参考元数据{doc.metadata}\n"

            source_name = os.path.basename(doc.metadata.get("source", "unknown"))
            sources_map[source_name].append({
                "index": counter,
                "rerank_score": round(doc.metadata.get("rerank_score", 0.0), 4),
                "snippet": doc.page_content[:100].replace("\n", " ") + "..."
            })

        sources = [
            {
                "source":name,
                "count": len(chunks),
                "max_score": max(c["rerank_score"] for c in chunks),
                "chunks" : chunks
            }
            for name, chunks in sources_map.items()
        ]
        sources.sort(key= lambda s: s["max_score"], reverse=True)

        ans = self.chain.invoke(
            {
                "input":query,
                "context":context
            }
        )
        return {
            "answer" : ans,
            "sources": sources,
            "has_reliable_source": True
        }

if __name__ == '__main__':
    rag_service = RagSummarizeService()
    print(rag_service.rag_summarize("最近我这个地区如何养护扫地机器人"))