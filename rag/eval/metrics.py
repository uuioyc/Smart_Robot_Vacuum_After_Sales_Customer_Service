"""
RAG 评测指标计算
"""
from typing import List, Dict

def recall_at_k(retrieved_sources: List[str], expected_source: str, k: int) -> float:
    return 1.0 if expected_source in retrieved_sources[:k] else 0.0


def mrr(retrieved_sources: List[str], expected_source: str) -> float:
    """
    MRR: 正确来源排在第几位，取倒数
    :param retrieved_sources: 查到的所有来源
    :param expected_source: 希望来源
    :return:
    """
    for i, src in enumerate(retrieved_sources, 1):
        #这个1是起始下标
        if src == expected_source:
            return 1.0 / i
    return 0.0

def aggregate_metrics(per_query_results: List[Dict]) -> Dict:
    n = len(per_query_results)
    if n == 0:
        return {}
    return{
        "总问题数": n,
        "Recall@5": sum(r["recall@5"] for r in per_query_results) / n,
        "MRR": sum(r["mrr"] for r in per_query_results) / n
    }