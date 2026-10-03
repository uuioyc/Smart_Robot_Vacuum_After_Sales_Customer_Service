import csv
import os.path
from datetime import datetime
from typing import List, Dict

from rag.eval.metrics import recall_at_k, aggregate_metrics
from rag.rag_service import RagSummarizeService
from rag.eval.metrics import mrr
from utils.log_handler import logger


class RAGEvaluator:
    def __init__(self, data_path: str):
        self.data_path = data_path
        self.rag_service = RagSummarizeService()

    def load_dataset(self) -> List[Dict]:
        """加载评测集"""
        with open(self.data_path, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))

    def evaluate_single(self, item: Dict) -> Dict:
        question = item["question"]
        expected_source = item["expected_source"]

        docs = self.rag_service.retriever_docs(question)

        retrieved_sources = [ #提取文件名
            os.path.basename(d.metadata.get("source", "unknown"))
            for d in docs
        ]

        return{
            "id": item["id"],
            "question": question,
            "intent": item["intent"],
            "difficulty": item["difficulty"],
            "expected_source":expected_source,
            "retrieved_sources" : retrieved_sources,
            "recall@5": recall_at_k(retrieved_sources, expected_source, 5),
            "mrr": mrr(retrieved_sources, expected_source)
        }

    def run(self, tag: str="baseline") -> Dict:
        """全量评测，输出报告"""
        dataset = self.load_dataset()
        logger.info(f"开始评测， 共{len(dataset)}条，tag={tag}")

        results = []
        for i, item in enumerate(dataset, 1):
            logger.info(f"[{i}/{len(dataset)}] : {item['question']}")
            results.append(self.evaluate_single(item))

        summary = aggregate_metrics(results)
        self._write_report(tag, summary, results)
        return summary
    def _write_report(self, tag: str, summary: Dict, results : List[Dict]):
        """输出markdown报告"""

        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        path = os.path.join(report_dir, f"{tag}_{timestamp}.md")

        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# RAG 评测报告 - {tag}\n\n")
            f.write(f"**评测时间**: {timestamp}\n")

            #指标
            f.write("## 汇总指标\n\n")
            f.write("| 指标 | 数值 | \n| :--- | :--- |\n")
            for k,v in summary.items():
                if k != '总问题数':
                    f.write(f"| {k} | {v :.4f} |\n")
                else:
                    f.write(f"| {k} | {v} |\n")

            f.write("\n## 失败案例(Recall@5 = 0)\n\n")
            fails = [r for r in results if r['recall@5'] == 0]
            f.write(f"共{len(fails)}条失败记录\n\n")
            for r in fails[:20]:
                f.write(f"- **Q{r['id']}** : {r['question']}\n")
                f.write(f"  - 期望：`{r['expected_source']}`\n")
                f.write(f"  - 实际：`{r['retrieved_sources']}`\n")

        logger.info(f"评测报告已生成：{path}")

if __name__ == '__main__':
    from utils.path_tool import get_abs_path

    evaluator = RAGEvaluator(get_abs_path("rag/eval/eval_dataset.csv"))
    summary = evaluator.run(tag="baseline")

    print("\n" + "=" * 40)
    print("Baseline 结果:", summary)
    print("=" * 40)