# rag/eval/generate_dataset.py
"""
RAG 评测集生成脚本
从知识库 chunk 反向生成口语化问题 + 精确答案片段

关键改进：
1. gold_answer 由 LLM 从原文摘抄，与 question 严格对应
2. expected_source 自动归一化为文件名（basename）
3. difficulty 强制分布控制（4:4:2）
4. intent 严格四分类
5. 生成后自动去重 + 输出质量报告
"""
import csv
import json
import os
import random
from collections import defaultdict, Counter
from pathlib import Path

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from model.factory import chat_model
from rag.vector_store import VectorStoreService
from utils.log_handler import logger


# ========== 生成 Prompt ==========
GENERATE_PROMPT = """你是一个扫地机器人售后领域的知识库构建专家。请根据下面这段资料，完成两个任务：

## 任务 1：生成一个真实用户会问的口语化问题
- 参考真实客服场景：用户不会用专业术语，会用"咋办""是不是坏了""能不能"等口语。
- 不要写成考试题或说明书标题。
- 例如：
  - ❌ "如何清洁LDS模组"（太书面）
  - ✅ "机器人转圈圈是不是坏了"（口语化）

## 任务 2：从资料中摘抄出能回答该问题的原文片段
- 必须**原文照抄**，不允许改写或概括。
- 只摘 1-2 句能直接回答问题的句子，不要整段复制。
- 如果资料中没有能回答该问题的内容，`gold_answer` 填 "NOT_FOUND"。

## 分类标签（必须严格从选项中选择）
- intent：故障排查 / 环境养护 / 选购咨询 / 耗材更换
- difficulty：
  - easy：单个知识点直接回答
  - medium：需要综合资料中 2-3 个知识点
  - hard：需要跨段落推理，或用户表述模糊需要先猜意图

【资料内容】
{content}

【来源文件】
{source}

【本次指定的难度】
{difficulty_target}

请严格输出 JSON（不要 ```json 包裹，不要其他文字）：
{{"question": "...", "gold_answer": "...", "intent": "...", "difficulty": "{difficulty_target}"}}
"""


def clean_json_str(s: str) -> str:
    """清洗 LLM 输出中的 markdown 代码块标记"""
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]           # 去掉第一行 ```json
        s = s.rsplit("```", 1)[0]          # 去掉最后的 ```
    return s.strip()


def sample_by_difficulty(n: int) -> list[str]:
    """
    按 4:4:2 生成难度序列
    n = 10 → ['easy']*4 + ['medium']*4 + ['hard']*2
    """
    easy_cnt = int(n * 0.4)
    medium_cnt = int(n * 0.4)
    hard_cnt = n - easy_cnt - medium_cnt
    seq = ["easy"] * easy_cnt + ["medium"] * medium_cnt + ["hard"] * hard_cnt
    random.shuffle(seq)
    return seq


def generate_dataset(chunks_per_file: int = 8, output_path: str = "rag/eval/eval_dataset.csv"):
    """
    从知识库每个文件抽 N 段，反向生成问题
    """
    # ========== 1. 从向量库拿所有 chunk ==========
    vs = VectorStoreService()
    store = vs.vector_store.get()
    documents = store.get("documents", [])
    metadatas = store.get("metadatas", [])

    if not documents:
        logger.error("向量库为空，无法生成数据集")
        return

    # ========== 2. 按 source 分组 ==========
    by_source = defaultdict(list)
    for content, meta in zip(documents, metadatas):
        source = os.path.basename(meta.get("source", "unknown"))
        by_source[source].append(content)

    logger.info(f"共 {len(by_source)} 个来源文件，总 chunk 数 {len(documents)}")

    # ========== 3. 组装链 ==========
    prompt = PromptTemplate.from_template(GENERATE_PROMPT)
    chain = prompt | chat_model | StrOutputParser()

    dataset = []
    idx = 1
    seen_questions = set()

    # ========== 4. 逐文件生成 ==========
    for source, chunks in by_source.items():
        sampled = random.sample(chunks, min(chunks_per_file, len(chunks)))
        difficulty_seq = sample_by_difficulty(len(sampled))

        for content, difficulty_target in zip(sampled, difficulty_seq):
            try:
                # 4.1 调用 LLM
                raw = chain.invoke({
                    "content": content[:1500],
                    "source": source,
                    "difficulty_target": difficulty_target
                })
                data = json.loads(clean_json_str(raw))

                # 4.2 过滤低质量数据
                question = data.get("question", "").strip()
                gold_answer = data.get("gold_answer", "").strip()

                if not question or gold_answer == "NOT_FOUND":
                    logger.warning(f"跳过（答案未找到）: {question}")
                    continue

                if question in seen_questions:
                    logger.warning(f"跳过（重复问题）: {question}")
                    continue

                seen_questions.add(question)

                # 4.3 写入
                dataset.append({
                    "id": idx,
                    "question": question,
                    "gold_answer": gold_answer,
                    "expected_source": source,
                    "intent": data.get("intent", "故障排查"),
                    "difficulty": data.get("difficulty", difficulty_target)
                })
                idx += 1
                logger.info(f"[{idx-1}] {question}")

            except json.JSONDecodeError as e:
                logger.warning(f"JSON 解析失败: {e} | 原始输出: {raw[:100]}")
            except Exception as e:
                logger.warning(f"生成失败: {e}")

    # ========== 5. 写入 CSV ==========
    if not dataset:
        logger.error("未生成任何数据")
        return

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "question", "gold_answer", "expected_source", "intent", "difficulty"]
        )
        writer.writeheader()
        writer.writerows(dataset)

    logger.info(f"✅ 共生成 {len(dataset)} 条数据，输出至 {output_path}")

    # ========== 6. 质量报告 ==========
    print_quality_report(dataset)


def print_quality_report(dataset: list[dict]):
    """打印质量分布报告"""
    print("\n" + "=" * 50)
    print(f"📊 数据集质量报告（共 {len(dataset)} 条）")
    print("=" * 50)

    intent_dist = Counter(d["intent"] for d in dataset)
    difficulty_dist = Counter(d["difficulty"] for d in dataset)
    source_dist = Counter(d["expected_source"] for d in dataset)

    print(f"\n【意图分布】")
    for k, v in intent_dist.most_common():
        pct = v / len(dataset) * 100
        print(f"  {k}: {v} 条 ({pct:.1f}%)")

    print(f"\n【难度分布】")
    for k in ["easy", "medium", "hard"]:
        v = difficulty_dist.get(k, 0)
        pct = v / len(dataset) * 100
        print(f"  {k}: {v} 条 ({pct:.1f}%)")

    print(f"\n【来源分布】")
    for k, v in source_dist.most_common():
        print(f"  {k}: {v} 条")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    from utils.path_tool import get_abs_path
    generate_dataset(chunks_per_file=8)