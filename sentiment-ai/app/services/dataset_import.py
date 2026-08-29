"""PulseCart 评论数据集导入与质量校验。

这个模块只负责文件边界和数据契约，不依赖 FastAPI、数据库或机器学习库，
因此可以在离线任务、API worker 和单元测试中复用。导入结果按数据内容和
字段映射生成稳定版本号，同一版本重复导入不会重复写入规范化记录。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


CANONICAL_FIELDS = (
    "review_id",
    "product_id",
    "review_text",
    "reviewed_at",
    "category_id",
    "channel",
    "rating",
    "product_version",
    "language",
)
REQUIRED_FIELDS = ("review_id", "product_id", "review_text", "reviewed_at")
ALLOWED_LANGUAGES = frozenset({"zh", "en", "mixed", "unknown"})

FIELD_ALIASES = {
    "review_id": ("id", "reviewId", "评论id", "评论编号"),
    "product_id": ("sku", "商品id", "商品编号"),
    "review_text": ("text", "review", "content", "评论", "评论内容"),
    "reviewed_at": ("date", "created_at", "reviewDate", "评论时间"),
    "category_id": ("category", "类目", "分类"),
    "channel": ("来源渠道",),
    "rating": ("score", "stars", "评分"),
    "product_version": ("version", "商品版本"),
    "language": ("lang", "语言"),
}


class DatasetImportError(ValueError):
    """输入文件无法满足数据契约。"""


@dataclass(frozen=True)
class ImportOptions:
    """导入质量规则，可通过任务配置覆盖但不能在模型推理中隐式改变。"""

    min_text_length: int = 1
    max_text_length: int = 5000
    reject_duplicate_text: bool = False

    def __post_init__(self) -> None:
        if self.min_text_length < 1:
            raise ValueError("min_text_length 必须大于 0")
        if self.max_text_length < self.min_text_length:
            raise ValueError("max_text_length 不能小于 min_text_length")


@dataclass(frozen=True)
class RejectedRow:
    row_number: int
    reason: str
    reasons: tuple[str, ...]
    details: str
    values: dict[str, str]


@dataclass(frozen=True)
class ImportReport:
    dataset_version: str
    idempotency_key: str
    file_sha256: str
    source_filename: str
    mapping: dict[str, str]
    quality_rules: dict[str, Any]
    received_rows: int
    valid_rows: int
    rejected_rows: int
    rejection_reasons: dict[str, int]
    duplicate_text_rows: int
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportResult:
    report: ImportReport
    records: list[dict[str, Any]]
    rejected: list[RejectedRow]
    reused: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = self.report.to_dict()
        result["reused"] = self.reused
        result["rejected"] = [asdict(row) for row in self.rejected]
        return result


def detect_language(text: str) -> str:
    """用可解释的字符比例做轻量语言标记，不把它冒充成语言模型结果。"""

    chinese = len(re.findall(r"[\u3400-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if chinese and latin:
        return "mixed"
    if chinese:
        return "zh"
    if latin:
        return "en"
    return "unknown"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_datetime(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed_date = date.fromisoformat(normalized)
        except ValueError:
            return None
        parsed = datetime.combine(parsed_date, time.min)
    return parsed.isoformat(timespec="seconds")


def _parse_rating(value: str) -> int | None:
    if not value.strip():
        return None
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation:
        return None
    if parsed != parsed.to_integral_value():
        return None
    rating = int(parsed)
    return rating if 1 <= rating <= 5 else None


def _normalise_header_lookup(headers: list[str]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for header in headers:
        key = header.strip()
        if not key:
            raise DatasetImportError("CSV 存在空列名")
        if key in lookup:
            raise DatasetImportError(f"CSV 存在重复列名: {key}")
        lookup[key] = header
    return lookup


def resolve_field_mapping(
    headers: list[str], field_mapping: Mapping[str, str] | None = None
) -> dict[str, str]:
    """将 canonical 字段映射到 CSV 原始列名。

    ``field_mapping`` 的方向固定为 ``{"review_text": "content"}``。
    未显式传入的字段按标准名和少量常见别名自动匹配，避免把列名猜测
    扩散到业务代码中。
    """

    header_lookup = _normalise_header_lookup(headers)
    requested = dict(field_mapping or {})
    unknown_fields = sorted(set(requested) - set(CANONICAL_FIELDS))
    if unknown_fields:
        raise DatasetImportError(f"字段映射包含未知标准字段: {', '.join(unknown_fields)}")

    resolved: dict[str, str] = {}
    for canonical in CANONICAL_FIELDS:
        source = requested.get(canonical)
        candidates = [source] if source else [canonical, *FIELD_ALIASES.get(canonical, ())]
        for candidate in candidates:
            if candidate is None:
                continue
            actual = header_lookup.get(str(candidate).strip())
            if actual is not None:
                resolved[canonical] = actual
                break

    missing = [field for field in REQUIRED_FIELDS if field not in resolved]
    if missing:
        raise DatasetImportError(f"缺少必填字段: {', '.join(missing)}")
    return resolved


class DatasetImporter:
    """导入 CSV 并在本地版本目录保存可复现的中间结果。"""

    def __init__(
        self,
        storage_dir: str | Path | None = None,
        options: ImportOptions | None = None,
    ) -> None:
        default_dir = Path(__file__).resolve().parents[2] / "data" / "imports"
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir
        self.options = options or ImportOptions()
        self._memory_cache: dict[str, ImportResult] = {}

    def import_file(
        self,
        file_path: str | Path,
        field_mapping: Mapping[str, str] | None = None,
    ) -> ImportResult:
        path = Path(file_path)
        if not path.is_file():
            raise DatasetImportError(f"找不到 CSV 文件: {path}")
        return self.import_bytes(
            path.read_bytes(),
            source_filename=path.name,
            field_mapping=field_mapping,
        )

    def import_bytes(
        self,
        content: bytes,
        *,
        source_filename: str = "reviews.csv",
        field_mapping: Mapping[str, str] | None = None,
    ) -> ImportResult:
        file_sha256 = hashlib.sha256(content).hexdigest()
        try:
            csv_text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DatasetImportError("CSV 必须使用 UTF-8 编码") from exc

        reader = csv.DictReader(io.StringIO(csv_text, newline=""))
        headers = list(reader.fieldnames or [])
        if not headers:
            raise DatasetImportError("CSV 缺少表头")
        mapping = resolve_field_mapping(headers, field_mapping)
        mapping_json = json.dumps(mapping, ensure_ascii=False, sort_keys=True)
        options_json = json.dumps(asdict(self.options), ensure_ascii=False, sort_keys=True)
        idempotency_key = hashlib.sha256(
            f"{file_sha256}\n{mapping_json}\n{options_json}".encode("utf-8")
        ).hexdigest()
        dataset_version = f"ds-{idempotency_key[:16]}"

        cached = self._memory_cache.get(idempotency_key)
        if cached:
            return ImportResult(cached.report, cached.records, cached.rejected, reused=True)
        persisted = self._load_persisted(dataset_version)
        if persisted:
            self._memory_cache[idempotency_key] = persisted
            return ImportResult(
                persisted.report, persisted.records, persisted.rejected, reused=True
            )

        result = self._process_rows(
            reader,
            mapping=mapping,
            file_sha256=file_sha256,
            idempotency_key=idempotency_key,
            dataset_version=dataset_version,
            source_filename=source_filename,
        )
        self._persist(result)
        self._memory_cache[idempotency_key] = result
        return result

    def _process_rows(
        self,
        reader: csv.DictReader,
        *,
        mapping: dict[str, str],
        file_sha256: str,
        idempotency_key: str,
        dataset_version: str,
        source_filename: str,
    ) -> ImportResult:
        records: list[dict[str, Any]] = []
        rejected: list[RejectedRow] = []
        seen_ids: set[str] = set()
        text_counts: Counter[str] = Counter()

        for row_number, raw_row in enumerate(reader, start=2):
            values = {
                canonical: _clean_text(raw_row.get(source, ""))
                for canonical, source in mapping.items()
            }
            errors: list[tuple[str, str]] = []
            extra_values = raw_row.get(None)
            if extra_values and any(_clean_text(value) for value in extra_values):
                errors.append(("extra_columns", "CSV 行包含未映射的额外字段"))
            review_id = values.get("review_id", "")
            if review_id in seen_ids and review_id:
                errors.append(("duplicate_review_id", "review_id 在文件内重复"))
            if review_id:
                seen_ids.add(review_id)

            for required in REQUIRED_FIELDS:
                if not values.get(required):
                    errors.append((f"missing_{required}", f"{required} 不能为空"))

            review_text = values.get("review_text", "")
            if review_text and len(review_text) < self.options.min_text_length:
                errors.append(("review_text_too_short", "review_text 长度过短"))
            if len(review_text) > self.options.max_text_length:
                errors.append(("review_text_too_long", "review_text 超过长度上限"))

            reviewed_at = _parse_datetime(values.get("reviewed_at", ""))
            if values.get("reviewed_at") and reviewed_at is None:
                errors.append(("invalid_reviewed_at", "reviewed_at 必须是 ISO 日期或时间"))

            rating_value = values.get("rating", "")
            rating = _parse_rating(rating_value) if rating_value else None
            if rating_value and rating is None:
                errors.append(("invalid_rating", "rating 必须是 1 到 5 的整数"))

            language = (values.get("language", "") or detect_language(review_text)).lower()
            if language not in ALLOWED_LANGUAGES:
                errors.append(("invalid_language", "language 必须是 zh/en/mixed/unknown"))

            if errors:
                reason, detail = errors[0]
                if len(errors) > 1:
                    detail += "; " + "; ".join(item[1] for item in errors[1:])
                rejected.append(
                    RejectedRow(
                        row_number=row_number,
                        reason=reason,
                        reasons=tuple(item[0] for item in errors),
                        details=detail,
                        values=values,
                    )
                )
                continue

            record: dict[str, Any] = {
                "review_id": review_id,
                "product_id": values["product_id"],
                "review_text": review_text,
                "reviewed_at": reviewed_at,
                "language": language,
            }
            if rating is not None:
                record["rating"] = rating
            for optional in ("category_id", "channel", "product_version"):
                if values.get(optional):
                    record[optional] = values[optional]

            text_counts[review_text] += 1
            if self.options.reject_duplicate_text and text_counts[review_text] > 1:
                rejected.append(
                    RejectedRow(
                        row_number=row_number,
                        reason="duplicate_review_text",
                        reasons=("duplicate_review_text",),
                        details="review_text 在文件内重复",
                        values=values,
                    )
                )
                continue
            records.append(record)

        duplicate_text_rows = sum(max(count - 1, 0) for count in text_counts.values())
        report = ImportReport(
            dataset_version=dataset_version,
            idempotency_key=idempotency_key,
            file_sha256=file_sha256,
            source_filename=source_filename,
            mapping=dict(mapping),
            quality_rules=asdict(self.options),
            received_rows=len(records) + len(rejected),
            valid_rows=len(records),
            rejected_rows=len(rejected),
            rejection_reasons=dict(
                Counter(reason for row in rejected for reason in row.reasons)
            ),
            duplicate_text_rows=duplicate_text_rows,
            created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )
        return ImportResult(report=report, records=records, rejected=rejected)

    def _persist(self, result: ImportResult) -> None:
        dataset_dir = self.storage_dir / result.report.dataset_version
        dataset_dir.mkdir(parents=True, exist_ok=True)
        (dataset_dir / "report.json").write_text(
            json.dumps(result.report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        with (dataset_dir / "records.jsonl").open("w", encoding="utf-8") as handle:
            for record in result.records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        (dataset_dir / "rejected.json").write_text(
            json.dumps([asdict(row) for row in result.rejected], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_persisted(self, dataset_version: str) -> ImportResult | None:
        dataset_dir = self.storage_dir / dataset_version
        report_path = dataset_dir / "report.json"
        records_path = dataset_dir / "records.jsonl"
        rejected_path = dataset_dir / "rejected.json"
        if not (report_path.is_file() and records_path.is_file() and rejected_path.is_file()):
            return None
        try:
            report = ImportReport(**json.loads(report_path.read_text(encoding="utf-8")))
            records = [
                json.loads(line)
                for line in records_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rejected = [
                RejectedRow(
                    row_number=item["row_number"],
                    reason=item["reason"],
                    reasons=tuple(item["reasons"]),
                    details=item["details"],
                    values=dict(item["values"]),
                )
                for item in json.loads(rejected_path.read_text(encoding="utf-8"))
            ]
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return ImportResult(report=report, records=records, rejected=rejected)


__all__ = [
    "ALLOWED_LANGUAGES",
    "CANONICAL_FIELDS",
    "DatasetImportError",
    "DatasetImporter",
    "ImportOptions",
    "ImportReport",
    "ImportResult",
    "REQUIRED_FIELDS",
    "RejectedRow",
    "detect_language",
    "resolve_field_mapping",
]
