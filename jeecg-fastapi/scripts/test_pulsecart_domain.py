"""PulseCart domain service checks using an in-memory SQLite database."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.models.base import Base
from app.models.pulsecart import PcDatasetImport, PcIssue, PcReview, PcReviewTask
from app.services.pulsecart_service import attach_reviews_to_tasks, task_to_dict, update_issue, update_review_task
from app.utils.common import new_id


def main() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[PcDatasetImport.__table__, PcReview.__table__, PcReviewTask.__table__, PcIssue.__table__],
    )
    session = sessionmaker(bind=engine)()
    session.add(PcDatasetImport(
        id=new_id(), dataset_version="ds-test-v1", source_filename="reviews.csv",
        file_sha256="a" * 64, mapping_json="{}", quality_rules_json="{}",
        rejection_reasons_json="{}", received_rows=30, valid_rows=30, rejected_rows=0,
    ))
    task = PcReviewTask(
        id=new_id(), task_id="task-1", dataset_version="ds-test-v1", review_id="review-1",
        sampling_group="risk_or_uncertainty", sampling_reason="low_model_confidence",
        system_aspects_json="[]", reviewer_aspects_json="[]", reviewer_note="",
    )
    matching_review = PcReview(
        id=new_id(), dataset_version="ds-test-v1", review_id="review-1", product_id="matching-product",
        review_text="导航连续碰撞", reviewed_at=datetime.now(UTC), language="zh-CN",
    )
    colliding_review = PcReview(
        id=new_id(), dataset_version="ds-test-v2", review_id="review-1", product_id="wrong-product",
        review_text="另一批数据中重复的编号", reviewed_at=datetime.now(UTC), language="zh-CN",
    )
    issue = PcIssue(
        id=new_id(), dataset_version="ds-test-v1", title="导航避障异常",
        aspect="navigation_obstacle_avoidance", severity="high", description="重复碰撞",
        source_review_ids_json=json.dumps(["review-1"], ensure_ascii=False),
    )
    session.add_all([task, issue, matching_review, colliding_review])
    session.commit()
    update_review_task(
        session, "task-1", status="approved", reviewer_sentiment="negative",
        reviewer_aspects=["navigation_obstacle_avoidance"], reviewer_note="已确认",
        reviewer_id="operator-1",
    )
    update_issue(session, issue.id, status="in_progress", resolution_note="已指派", owner_user_id="owner-1")
    update_issue(session, issue.id, status="pending_validation", resolution_note="修复待验证", owner_user_id=None)
    update_issue(session, issue.id, status="closed", resolution_note="回归验证通过", owner_user_id=None)
    assert task_to_dict(task)["review_status"] == "approved"
    task_with_evidence = attach_reviews_to_tasks([task], [colliding_review, matching_review])[0]
    assert task_with_evidence["review"]["product_id"] == "matching-product"
    assert session.get(PcIssue, issue.id).status == "closed"
    print("PulseCart domain checks passed")


if __name__ == "__main__":
    main()
