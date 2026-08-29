"""Train a PulseCart sentiment baseline from completed human review tasks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.baseline_sentiment import load_reviewed_records, train_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="从人工审核任务训练 PulseCart 三分类情感基线")
    parser.add_argument("--reviews", required=True, help="规范化评论 CSV")
    parser.add_argument("--review-tasks", required=True, help="已审核任务 JSONL")
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output-dir", required=True, help="模型运行输出目录")
    parser.add_argument("--seed", type=int, default=68)
    args = parser.parse_args()

    records = load_reviewed_records(args.reviews, args.review_tasks)
    result = train_baseline(
        records,
        args.output_dir,
        dataset_version=args.dataset_version,
        random_seed=args.seed,
    )
    print(
        json.dumps(
            {
                "model_path": str(result.model_path),
                "metadata_path": str(result.metadata_path),
                "training_records": result.training_records,
                "test_records": result.test_records,
                "metrics": result.metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
