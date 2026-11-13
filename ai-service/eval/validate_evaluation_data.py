"""Validate evaluation data and make its evidence boundary explicit."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST = EVAL_DIR / "evaluation_manifest.json"
RESULT_PATH = EVAL_DIR / "results" / "dataset_validation.json"
ALLOWED_CATEGORIES = {"exact", "paraphrase", "symptom", "offtopic"}


def normalized(text: str) -> str:
    return re.sub(r"[^\w]+", "", text.strip().casefold())


def validate(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    datasets: list[dict] = []

    for spec in manifest.get("datasets", []):
        path = EVAL_DIR / spec["path"]
        if not path.exists():
            errors.append(f"missing dataset: {path.name}")
            continue
        try:
            cases = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid UTF-8/JSON in {path.name}: {exc}")
            continue
        if not isinstance(cases, list):
            errors.append(f"{path.name} must contain a JSON array")
            continue

        ids = [str(case.get("id", "")).strip() for case in cases]
        counts = Counter(str(case.get("category", "")) for case in cases)
        duplicate_ids = sorted(k for k, n in Counter(ids).items() if k and n > 1)
        blank_ids = sum(not item for item in ids)
        invalid_categories = sorted(set(counts) - ALLOWED_CATEGORIES)
        query_groups: dict[str, list[str]] = defaultdict(list)

        for idx, case in enumerate(cases):
            query = case.get("query")
            expected = case.get("expected")
            category = case.get("category")
            if not isinstance(query, str) or not query.strip():
                errors.append(f"{path.name}[{idx}] has an empty/non-string query")
            else:
                query_groups[normalized(query)].append(ids[idx] or f"row_{idx}")
            if category == "offtopic":
                if expected not in ("", None):
                    errors.append(f"{path.name}[{idx}] offtopic case must have empty expected")
            elif category in ALLOWED_CATEGORIES:
                if not isinstance(expected, str) or not expected.strip():
                    errors.append(f"{path.name}[{idx}] answerable case has empty expected")

        if blank_ids:
            errors.append(f"{path.name} has {blank_ids} blank ids")
        if duplicate_ids:
            errors.append(f"{path.name} has duplicate ids: {duplicate_ids}")
        if invalid_categories:
            errors.append(f"{path.name} has invalid categories: {invalid_categories}")
        if len(cases) != spec.get("expected_size"):
            errors.append(
                f"{path.name} size={len(cases)}, expected={spec.get('expected_size')}"
            )
        expected_distribution = spec.get("expected_distribution", {})
        for category, expected_count in expected_distribution.items():
            if counts.get(category, 0) != expected_count:
                errors.append(
                    f"{path.name} {category}={counts.get(category, 0)}, expected={expected_count}"
                )
        duplicate_queries = {
            query: case_ids for query, case_ids in query_groups.items() if query and len(case_ids) > 1
        }
        if duplicate_queries:
            warnings.append(
                f"{path.name} has {len(duplicate_queries)} normalized duplicate queries"
            )
        if not spec.get("independent_annotation", False):
            warnings.append(
                f"{path.name} is not independently annotated; use it only as a development/ablation set"
            )

        datasets.append(
            {
                "path": spec["path"],
                "role": spec.get("role"),
                "num_cases": len(cases),
                "distribution": dict(sorted(counts.items())),
                "answerable": len(cases) - counts.get("offtopic", 0),
                "duplicate_ids": duplicate_ids,
                "normalized_duplicate_queries": duplicate_queries,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "independent_annotation": bool(spec.get("independent_annotation", False)),
            }
        )

    return {
        "valid": not errors,
        "manifest": manifest_path.name,
        "errors": errors,
        "warnings": warnings,
        "datasets": datasets,
        "claim_boundary": manifest.get("evaluation_policy", {}).get("claim_boundary"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=RESULT_PATH)
    args = parser.parse_args()
    report = validate(args.manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
