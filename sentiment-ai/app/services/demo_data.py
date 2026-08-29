"""Generate deterministic, clearly synthetic PulseCart demo data.

The generated files exercise the import, review and evaluation flows. They are
not customer data and must not be used to claim real-world model performance.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any


GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20260828
DEFAULT_REVIEW_COUNT = 1200
DEFAULT_REVIEW_TASK_COUNT = 300

SENTIMENTS = ("positive", "neutral", "negative")
ASPECTS = (
    "cleaning_effectiveness",
    "navigation_obstacle_avoidance",
    "noise",
    "battery_and_docking",
    "mopping",
    "app_and_connectivity",
    "reliability_and_failures",
    "setup_and_usability",
    "packaging_and_delivery",
    "after_sales_service",
    "value_for_money",
)
HIGH_RISK_ASPECTS = {
    "navigation_obstacle_avoidance",
    "reliability_and_failures",
    "after_sales_service",
}
PRODUCTS = (
    {"product_id": "JC-S1-LITE", "product_name": "净界 S1 Lite", "versions": ("1.0.0", "1.1.0")},
    {"product_id": "JC-S2-PRO", "product_name": "净界 S2 Pro", "versions": ("2.0.0", "2.1.0")},
    {"product_id": "JC-X3-MAX", "product_name": "净界 X3 Max", "versions": ("3.0.0", "3.1.0")},
)
CHANNELS = ("天猫旗舰店", "京东自营", "抖音商城", "品牌小程序")

# The short clauses are deliberately written as product feedback, not copied
# platform reviews. A suffix supplies variation without turning fields into PII.
TEMPLATES: dict[str, dict[str, tuple[str, ...]]] = {
    "cleaning_effectiveness": {
        "positive": ("地板上的灰尘和头发基本一次就能收干净", "沿墙清扫比预期细致，桌脚附近也处理到了"),
        "neutral": ("日常灰尘能清理，墙边偶尔还要手动补一下", "清洁效果符合预期，顽固污渍需要多跑一遍"),
        "negative": ("墙边和桌脚附近漏扫比较明显", "清扫后仍有不少头发残留，需要重复运行"),
    },
    "navigation_obstacle_avoidance": {
        "positive": ("识别椅脚和拖鞋很稳，没有乱撞", "地图建立很快，绕开电线的表现不错"),
        "neutral": ("大部分障碍物能绕开，地毯边缘偶尔会犹豫", "路线基本正常，复杂房间会多绕一圈"),
        "negative": ("更新后经常撞到椅脚，还会在门口反复打转", "识别不到地上的电线，导航路线明显变乱"),
    },
    "noise": {
        "positive": ("标准档声音可以接受，晚上也不会太打扰", "运行声比较轻，开会时放在客厅问题不大"),
        "neutral": ("普通档还好，强力档声音明显一些", "噪音在可接受范围，夜间不太适合开强力模式"),
        "negative": ("强力档噪音很大，隔着房门都能听见", "回充时提示音偏响，夜里容易被吵到"),
    },
    "battery_and_docking": {
        "positive": ("两居室一次能完成，电量还有余量", "低电量后能自己找到基站并继续任务"),
        "neutral": ("小户型续航足够，大户型会中途回充一次", "回充大多数时候正常，偶尔要等几秒才对准"),
        "negative": ("电量掉得很快，半个小时就要回充", "有时找不到基站，停在旁边也不回去"),
    },
    "mopping": {
        "positive": ("日常水印和脚印能拖掉，出水比较均匀", "拖地后地面不黏，维护也比较方便"),
        "neutral": ("轻微污渍能处理，厨房油点还是要手动擦", "出水量合适，但边角拖不到"),
        "negative": ("拖布出水不均，有的区域几乎没拖到", "拖完留下明显水痕，地面干得很慢"),
    },
    "app_and_connectivity": {
        "positive": ("App 配网顺利，分区和禁区设置很直观", "远程查看地图和预约任务都很稳定"),
        "neutral": ("常用功能够用，地图加载偶尔会慢一点", "第一次配网花了点时间，之后使用正常"),
        "negative": ("App 经常提示设备离线，重新配网也不稳定", "地图同步失败后无法设置禁区，影响使用"),
    },
    "reliability_and_failures": {
        "positive": ("连续用了几周没有报错，集尘和清扫都稳定", "日常运行可靠，耗材提醒也比较准确"),
        "neutral": ("整体能用，偶尔提示传感器需要擦拭", "运行比较稳定，但有一次任务中断后需要重启"),
        "negative": ("用了不久就频繁报传感器错误，任务会中断", "机器会无故停下，重启后问题还会出现"),
    },
    "setup_and_usability": {
        "positive": ("开箱到完成建图很顺，说明步骤清楚", "按键和耗材拆装都好理解，家里人也会用"),
        "neutral": ("首次设置步骤较多，但照着提示能完成", "功能不少，需要花时间熟悉不同模式"),
        "negative": ("首次建图提示不够清楚，反复失败才完成", "尘盒和拖布拆装很紧，长辈不太好操作"),
    },
    "packaging_and_delivery": {
        "positive": ("包装结实，配件齐全，到货外观没有损伤", "发货及时，外箱和机器保护都做得很好"),
        "neutral": ("到货时间正常，包装没有问题", "配件齐全，外箱有轻微压痕但不影响使用"),
        "negative": ("外箱破损明显，拆开后发现配件少了一件", "物流等待时间长，收到时机器边角有划痕"),
    },
    "after_sales_service": {
        "positive": ("客服响应快，按指引很快解决了问题", "售后换件流程清楚，进度也会主动通知"),
        "neutral": ("客服能解答问题，处理进度需要自己追问", "售后流程可以接受，等待时间比预期长一点"),
        "negative": ("客服反复让重置设备，问题一直没有解决", "申请维修后迟迟没有明确进度，沟通成本很高"),
    },
    "value_for_money": {
        "positive": ("同价位功能完整，日常省下不少时间", "功能和做工对得起价格，整体比较值"),
        "neutral": ("价格不算低，但功能基本符合预期", "促销入手还可以，原价购买需要再比较"),
        "negative": ("价格不低但稳定性一般，感觉不够值", "基础功能体验不稳，和这个价位不太匹配"),
    },
}
RATING_BY_SENTIMENT = {
    "positive": (4, 5),
    "neutral": (3,),
    "negative": (1, 2),
}
SENTIMENT_WEIGHTS = (52, 20, 28)


@dataclass(frozen=True)
class DemoGenerationResult:
    output_dir: Path
    reviews_path: Path
    review_tasks_path: Path
    reference_labels_path: Path
    manifest_path: Path
    review_count: int
    review_task_count: int


def _weighted_sentiment(randomizer: random.Random) -> str:
    return randomizer.choices(SENTIMENTS, weights=SENTIMENT_WEIGHTS, k=1)[0]


def _date_for_index(index: int, randomizer: random.Random) -> date:
    start = date(2026, 4, 1)
    # One hundred and twenty days exposes a realistic time-window comparison.
    return start + timedelta(days=(index * 7 + randomizer.randrange(0, 11)) % 120)


def _choose_aspect(
    randomizer: random.Random,
    *,
    sentiment: str,
    product_id: str,
    product_version: str,
    reviewed_at: date,
) -> str:
    # A seeded, documented scenario: S2 Pro 2.1.0 navigation complaints rise
    # after July. This gives the insight view a legitimate demo signal to find.
    if (
        sentiment == "negative"
        and product_id == "JC-S2-PRO"
        and product_version == "2.1.0"
        and reviewed_at >= date(2026, 7, 1)
        and randomizer.random() < 0.58
    ):
        return "navigation_obstacle_avoidance"
    return randomizer.choice(ASPECTS)


def _make_text(
    randomizer: random.Random,
    *,
    product_name: str,
    aspect: str,
    sentiment: str,
    channel: str,
) -> str:
    opening = randomizer.choice((f"{product_name}用了几天，", "这台扫地机器人到手后，", "家里使用一段时间后，", "结合日常清扫情况，"))
    clause = randomizer.choice(TEMPLATES[aspect][sentiment])
    closing = randomizer.choice(
        (
            "，这是我这次最明显的感受。",
            "，希望后续版本能保持或改进。",
            f"，在{channel}购买的这台用于日常家用。",
            "，记录下来给同样需求的人参考。",
        )
    )
    return f"{opening}{clause}{closing}"


def _make_system_prediction(
    randomizer: random.Random,
    *,
    expected_sentiment: str,
    expected_aspects: tuple[str, ...],
) -> tuple[str, tuple[str, ...], float]:
    incorrect = randomizer.random() < 0.18
    if incorrect:
        predicted_sentiment = randomizer.choice(
            tuple(item for item in SENTIMENTS if item != expected_sentiment)
        )
        predicted_aspect = randomizer.choice(
            tuple(item for item in ASPECTS if item not in expected_aspects)
        )
        confidence = round(randomizer.uniform(0.44, 0.68), 3)
    else:
        predicted_sentiment = expected_sentiment
        predicted_aspect = expected_aspects[0]
        confidence = round(randomizer.uniform(0.63, 0.97), 3)
    return predicted_sentiment, (predicted_aspect,), confidence


def _build_reviews(total_reviews: int, seed: int) -> tuple[list[dict[str, str]], dict[str, dict[str, Any]]]:
    randomizer = random.Random(seed)
    reviews: list[dict[str, str]] = []
    oracle: dict[str, dict[str, Any]] = {}
    used_texts: set[str] = set()

    for index in range(total_reviews):
        product = PRODUCTS[index % len(PRODUCTS)]
        reviewed_at = _date_for_index(index, randomizer)
        product_version = randomizer.choice(product["versions"])
        sentiment = _weighted_sentiment(randomizer)
        aspect = _choose_aspect(
            randomizer,
            sentiment=sentiment,
            product_id=product["product_id"],
            product_version=product_version,
            reviewed_at=reviewed_at,
        )
        channel = randomizer.choice(CHANNELS)
        text = _make_text(
            randomizer,
            product_name=product["product_name"],
            aspect=aspect,
            sentiment=sentiment,
            channel=channel,
        )
        # Preserve deterministic uniqueness without fabricating personal data.
        if text in used_texts:
            text = f"{text} 体验记录 {index + 1}。"
        used_texts.add(text)

        review_id = f"demo-sr-{index + 1:04d}"
        expected_aspects = (aspect,)
        system_sentiment, system_aspects, confidence = _make_system_prediction(
            randomizer,
            expected_sentiment=sentiment,
            expected_aspects=expected_aspects,
        )
        reviews.append(
            {
                "review_id": review_id,
                "product_id": product["product_id"],
                "category_id": "sweep_robot",
                "review_text": text,
                "reviewed_at": reviewed_at.isoformat(),
                "channel": channel,
                "rating": str(randomizer.choice(RATING_BY_SENTIMENT[sentiment])),
                "product_version": product_version,
                "language": "zh",
            }
        )
        oracle[review_id] = {
            "synthetic_reference_sentiment": sentiment,
            "synthetic_reference_aspects": list(expected_aspects),
            "system_sentiment": system_sentiment,
            "system_aspects": list(system_aspects),
            "system_confidence": confidence,
        }
    return reviews, oracle


def _select_review_tasks(
    reviews: list[dict[str, str]],
    oracle: dict[str, dict[str, Any]],
    *,
    task_count: int,
    seed: int,
) -> list[dict[str, Any]]:
    if task_count <= 0 or task_count > len(reviews):
        raise ValueError("review_task_count 必须大于 0 且不超过评论总数")
    priority_count = task_count // 2
    review_by_id = {review["review_id"]: review for review in reviews}

    candidates: list[tuple[int, str, str]] = []
    for review in reviews:
        review_id = review["review_id"]
        reference = oracle[review_id]
        aspect = reference["synthetic_reference_aspects"][0]
        is_risk_negative = (
            reference["synthetic_reference_sentiment"] == "negative"
            and aspect in HIGH_RISK_ASPECTS
        )
        is_low_confidence = reference["system_confidence"] < 0.69
        if is_risk_negative or is_low_confidence:
            reason = "risk_negative_attribute" if is_risk_negative else "low_model_confidence"
            score = 0 if is_risk_negative else 1
            candidates.append((score, review_id, reason))

    candidates.sort(key=lambda item: (item[0], item[1]))
    priority_ids: dict[str, str] = {}
    for _, review_id, reason in candidates:
        if len(priority_ids) == priority_count:
            break
        priority_ids[review_id] = reason
    if len(priority_ids) < priority_count:
        raise ValueError("高优先级审核候选不足，无法生成固定审核任务")

    randomizer = random.Random(seed + 1)
    buckets: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for review in reviews:
        review_id = review["review_id"]
        if review_id in priority_ids:
            continue
        reference = oracle[review_id]
        month = review["reviewed_at"][:7]
        bucket_key = (
            review["product_id"],
            review["channel"],
            month,
            reference["synthetic_reference_sentiment"],
        )
        buckets[bucket_key].append(review_id)
    for bucket in buckets.values():
        randomizer.shuffle(bucket)

    random_ids: list[str] = []
    bucket_keys = sorted(buckets)
    while len(random_ids) < task_count - priority_count:
        progressed = False
        for key in bucket_keys:
            if buckets[key]:
                random_ids.append(buckets[key].pop())
                progressed = True
                if len(random_ids) == task_count - priority_count:
                    break
        if not progressed:
            raise ValueError("分层随机样本不足，无法生成固定审核任务")

    tasks: list[dict[str, Any]] = []
    selected = [(review_id, "risk_or_uncertainty", reason) for review_id, reason in priority_ids.items()]
    selected.extend((review_id, "stratified_random", "stratified_sample") for review_id in random_ids)
    for task_number, (review_id, sampling_group, sampling_reason) in enumerate(selected, start=1):
        reference = oracle[review_id]
        tasks.append(
            {
                "task_id": f"review-task-{task_number:04d}",
                "review_id": review_id,
                "sampling_group": sampling_group,
                "sampling_reason": sampling_reason,
                "assigned_role": "product_operator",
                "review_status": "pending",
                "model_version": "demo-rule-v0",
                "system_sentiment": reference["system_sentiment"],
                "system_aspects": reference["system_aspects"],
                "system_confidence": reference["system_confidence"],
                "reviewer_sentiment": None,
                "reviewer_aspects": [],
                "reviewer_note": "",
                "source_snapshot": {
                    "product_id": review_by_id[review_id]["product_id"],
                    "product_version": review_by_id[review_id]["product_version"],
                    "channel": review_by_id[review_id]["channel"],
                    "reviewed_at": review_by_id[review_id]["reviewed_at"],
                },
            }
        )
    return tasks


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_demo_dataset(
    output_dir: str | Path,
    *,
    total_reviews: int = DEFAULT_REVIEW_COUNT,
    review_task_count: int = DEFAULT_REVIEW_TASK_COUNT,
    seed: int = DEFAULT_SEED,
) -> DemoGenerationResult:
    """Write a deterministic synthetic review dataset and its review-work queue."""
    if total_reviews < 20:
        raise ValueError("total_reviews 至少为 20，才能保持演示数据分布")
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    reviews, oracle = _build_reviews(total_reviews, seed)
    tasks = _select_review_tasks(reviews, oracle, task_count=review_task_count, seed=seed)

    reviews_path = output_path / "reviews.csv"
    review_tasks_path = output_path / "review_tasks.jsonl"
    reference_labels_path = output_path / "synthetic_reference_labels.jsonl"
    manifest_path = output_path / "manifest.json"
    fieldnames = (
        "review_id",
        "product_id",
        "category_id",
        "review_text",
        "reviewed_at",
        "channel",
        "rating",
        "product_version",
        "language",
    )
    with reviews_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reviews)

    _write_jsonl(review_tasks_path, tasks)
    _write_jsonl(
        reference_labels_path,
        [
            {
                "review_id": review_id,
                **reference,
                "notice": "Synthetic reference only. Do not treat as human-reviewed ground truth.",
            }
            for review_id, reference in sorted(oracle.items())
        ],
    )
    sentiment_counts = Counter(
        reference["synthetic_reference_sentiment"] for reference in oracle.values()
    )
    aspect_counts = Counter(
        reference["synthetic_reference_aspects"][0] for reference in oracle.values()
    )
    manifest = {
        "dataset_name": "净界智能扫地机器人合成评论演示集",
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "is_synthetic": True,
        "intended_use": "PulseCart 本地导入、审核队列、分析与界面演示",
        "prohibited_use": "不得用于宣称真实电商用户表现、线上模型效果或商业结论",
        "review_count": total_reviews,
        "review_task_count": review_task_count,
        "review_task_split": {"risk_or_uncertainty": review_task_count // 2, "stratified_random": review_task_count - review_task_count // 2},
        "sentiment_counts": dict(sorted(sentiment_counts.items())),
        "aspect_counts": dict(sorted(aspect_counts.items())),
        "scenario": "JC-S2-PRO 2.1.0 在 2026-07-01 后的负面导航避障信号上升，用于验证趋势与问题候选页面。",
        "files": {
            "reviews.csv": _file_sha256(reviews_path),
            "review_tasks.jsonl": _file_sha256(review_tasks_path),
            "synthetic_reference_labels.jsonl": _file_sha256(reference_labels_path),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return DemoGenerationResult(
        output_dir=output_path,
        reviews_path=reviews_path,
        review_tasks_path=review_tasks_path,
        reference_labels_path=reference_labels_path,
        manifest_path=manifest_path,
        review_count=total_reviews,
        review_task_count=review_task_count,
    )


__all__ = [
    "ASPECTS",
    "DEFAULT_REVIEW_COUNT",
    "DEFAULT_REVIEW_TASK_COUNT",
    "DEFAULT_SEED",
    "DemoGenerationResult",
    "GENERATOR_VERSION",
    "generate_demo_dataset",
]
