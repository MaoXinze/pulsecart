"""Execute queued PulseCart baseline-training jobs.

Use one worker process in local dev/demo mode.  Production replaces this
filesystem queue with the same job contract on Redis.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.training_jobs import TrainingJobStore


def main() -> None:
    parser = argparse.ArgumentParser(description="执行一个或多个 PulseCart 模型训练任务")
    parser.add_argument("--limit", type=int, default=1, help="本次最多执行的排队任务数")
    args = parser.parse_args()
    if args.limit < 1:
        raise SystemExit("--limit 必须大于 0")
    store = TrainingJobStore(settings.training_job_root, settings.model_root)
    processed = []
    for _ in range(args.limit):
        job = store.execute_next()
        if job is None:
            break
        processed.append({
            "job_id": job["job_id"],
            "status": job["status"],
            "model_version": job["model_version"],
            "error_message": job["error_message"],
        })
    print(json.dumps({"processed": processed}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
