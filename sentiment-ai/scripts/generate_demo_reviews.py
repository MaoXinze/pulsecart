"""Generate the checked-in PulseCart synthetic demo dataset."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.demo_data import (
    DEFAULT_REVIEW_COUNT,
    DEFAULT_REVIEW_TASK_COUNT,
    DEFAULT_SEED,
    generate_demo_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 PulseCart 合成扫地机器人评论演示数据")
    parser.add_argument("--output-dir", default=str(ROOT / "data" / "demo" / "sweep_robot"))
    parser.add_argument("--review-count", type=int, default=DEFAULT_REVIEW_COUNT)
    parser.add_argument("--review-task-count", type=int, default=DEFAULT_REVIEW_TASK_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args()

    result = generate_demo_dataset(
        args.output_dir,
        total_reviews=args.review_count,
        review_task_count=args.review_task_count,
        seed=args.seed,
    )
    print(
        {
            "output_dir": str(result.output_dir),
            "review_count": result.review_count,
            "review_task_count": result.review_task_count,
            "reviews": str(result.reviews_path),
            "tasks": str(result.review_tasks_path),
            "manifest": str(result.manifest_path),
        }
    )


if __name__ == "__main__":
    main()
