"""
RRF (Reciprocal Rank Fusion) 融合多路检索结果
涉及 错误码、缩写、型号 BM25更好一些
涉及 口语化表述，语义改写 向量更好一些
第一，用 IDF 衡量词的稀有度，稀有词权重更高；
第二，对词频做了饱和处理——一个词出现 3 次和出现 10 次得分差距很小，
防止某一个词出现次数过多，影响结果；
第三，引入文档长度归一化，长文档不再占便宜。一篇 200 字的文档命中"E12"，比 2000 字里提到"E12"的文档更可信。
所以 BM25 在处理错误码、型号这类稀有 token 时特别精准，
这也是我把它和向量检索结合起来做混合检索的原因。
"""

from langchain_core.documents import Document


def rrf_fusion(
        doc_lists: list[list[Document]],
        k: int = 60,
        top_n: int = 20,
) -> list[Document]:
    """
    RRF融合多路检索结果
    :param doc_list: 多路检索结果，每个元素是一路检索的Document列表
    :param k: 平滑常数，一般取60
    :param top_n: 融合后返回的文档数
    :return: 融合后按RRF降序排列的Document列表
    """
    scores = {}
    doc_map = {} #用于Document去重

    """
        这是多路检索，到最后要融合成一个top_n的序列
        对于每个chunk，他的得分是每一路里面的得分加起来
        每一路的得分就是 1 / (k + rank), k = 60是经验值
    """
    for doc_list in doc_lists:
        for rank, doc in enumerate(doc_list, 1):
            key = doc.page_content #用内容做唯一标识
            if key not in doc_map:
                doc_map[key] = doc
                scores[key] = 0.0
            scores[key] += 1.0 / (k + rank)
    #用key做标识，最后得到的内容一定是去重的，此时再排序即可

    #按RRF 分数降序
    sorted_keys = sorted(scores.keys(), key = lambda x : scores[x], reverse=True)

    result = [doc_map[key] for key in sorted_keys[:top_n]]

    for doc in result:
        doc.metadata["rrf_score"] = round(scores[key], 6)
    #本项目是两路融合，理论最高分只有0.0328
    return result