import csv
import os
from datetime import datetime
from collections import defaultdict, Counter

from rag.router import IntentRouter
from utils.log_handler import logger


class IntentEvaluator:
    def __init__(self, dataset_path: str):
        self.dataset_path = dataset_path
        self.router = IntentRouter()

    def load_dataset(self):
        with open(self.dataset_path, 'r', encoding='utf-8') as f:
            return list(csv.DictReader(f))

    def evaluate(self):
        data = self.load_dataset()
        results = []

        for i, item in enumerate(data, 1):
            question = item["question"]
            expected = item["expected_intent"]

            try:
                pred = self.router.classify(question)
                predicted = pred.intent
                confidence = pred.confidence
            except Exception as e:
                predicted = "ERROR"
                confidence = 0.0
                logger.error(f"分类失败: {e}")

            results.append({
                "question": question,
                "expected": expected,
                "predicted": predicted,
                "confidence": confidence,
                "correct": predicted == expected
            })
            logger.info(
                f"[{i}/{len(data)}] {question} | 期望={expected} | 预测={predicted} | {'✅' if predicted == expected else '❌'}")

        # 统计
        accuracy = sum(r["correct"] for r in results) / len(results)

        # 每类指标
        per_class = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "total": 0})
        for r in results:
            exp, pred = r["expected"], r["predicted"]
            per_class[exp]["total"] += 1
            if exp == pred:
                per_class[exp]["tp"] += 1
            else:
                per_class[exp]["fn"] += 1
                per_class[pred]["fp"] += 1

        return {
            "accuracy": accuracy,
            "total": len(results),
            "results": results,
            "per_class": dict(per_class)
        }

    def write_report(self, summary):
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(report_dir, f"intent_accuracy_{timestamp}.md")

        with open(path, 'w', encoding='utf-8') as f:
            f.write(f"# 意图识别准确率评测报告\n\n")
            f.write(f"**评测时间**: {timestamp}\n\n")
            f.write(f"## 汇总\n\n")
            f.write(f"- 总问题数：{summary['total']}\n")
            f.write(f"- 准确率：**{summary['accuracy']:.2%}**\n\n")

            f.write("## 每类意图指标\n\n")
            f.write("| 意图 | 总数 | 正确 | 召回率 |\n| :--- | :--- | :--- | :--- |\n")
            for intent, m in summary["per_class"].items():
                recall = m["tp"] / m["total"] if m["total"] else 0
                f.write(f"| {intent} | {m['total']} | {m['tp']} | {recall:.2%} |\n")

            f.write("\n## 错误案例\n\n")
            errors = [r for r in summary["results"] if not r["correct"]]
            f.write(f"共 {len(errors)} 条错误\n\n")
            for r in errors:
                f.write(f"- **{r['question']}**\n")
                f.write(f"  - 期望：`{r['expected']}`\n")
                f.write(f"  - 预测：`{r['predicted']}` (置信度 {r['confidence']:.2f})\n\n")

        return path


if __name__ == "__main__":
    from utils.path_tool import get_abs_path

    evaluator = IntentEvaluator(get_abs_path("agent/eval/intent_eval_dataset.csv"))
    summary = evaluator.evaluate()

    print(f"\n{'=' * 40}")
    print(f"意图识别准确率: {summary['accuracy']:.2%} ({summary['total']} 条)")
    print(f"{'=' * 40}")

    path = evaluator.write_report(summary)
    print(f"报告: {path}")