"""导入 PulseCart 评论 CSV，并输出可追溯的数据质量报告。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 允许从仓库根目录或 sentiment-ai 目录直接执行脚本。
AI_ROOT = Path(__file__).resolve().parents[1]
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from app.services.dataset_import import DatasetImporter


def main() -> None:
    parser = argparse.ArgumentParser(description="Import and validate PulseCart reviews")
    parser.add_argument("csv_file", type=Path)
    parser.add_argument(
        "--storage-dir",
        type=Path,
        default=None,
        help="版本化导入产物目录，默认写入 data/imports",
    )
    parser.add_argument(
        "--mapping",
        action="append",
        default=[],
        metavar="CANONICAL=SOURCE",
        help="字段映射，例如 review_text=content，可重复传入",
    )
    args = parser.parse_args()
    mapping = {}
    for item in args.mapping:
        canonical, separator, source = item.partition("=")
        if not separator or not canonical.strip() or not source.strip():
            parser.error(f"字段映射格式错误: {item}")
        mapping[canonical.strip()] = source.strip()

    result = DatasetImporter(args.storage_dir).import_file(
        args.csv_file,
        field_mapping=mapping or None,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
