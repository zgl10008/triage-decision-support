"""One reproducible entry point for the project's evaluation scripts."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


EVAL_DIR = Path(__file__).resolve().parent
ROOT_DIR = EVAL_DIR.parent
RESULTS_DIR = EVAL_DIR / "results"
MANIFEST_PATH = EVAL_DIR / "evaluation_manifest.json"
RUN_RESULT = RESULTS_DIR / "system_evaluation_run.json"
SUMMARY_PATH = RESULTS_DIR / "system_evaluation_summary.md"


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def package_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def run_script(script: Path, extra_args: list[str] | None = None) -> dict:
    started = time.perf_counter()
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(script), *(extra_args or [])],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    return {
        "status": "passed" if proc.returncode == 0 else "failed",
        "exit_code": proc.returncode,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def render_summary(run: dict, manifest: dict) -> str:
    validation = load_json(RESULTS_DIR / "dataset_validation.json")
    retrieval = load_json(RESULTS_DIR / "retrieval_ablation.json")
    agentic = load_json(RESULTS_DIR / "agentic_ablation.json")
    safety = load_json(RESULTS_DIR / "safety_evaluation.json")
    efficiency = load_json(RESULTS_DIR / "efficiency_evaluation.json")
    lines = [
        "# 系统评测摘要",
        "",
        f"- 运行时间（UTC）：{run['started_at_utc']}",
        f"- Python：{run['python']}",
        f"- 数据校验：{'通过' if validation.get('valid') else '未通过'}",
        f"- 证据边界：{manifest['evaluation_policy']['claim_boundary']}",
        "",
        "## 本次执行状态",
        "",
        "| 组件 | 状态 | 耗时（秒） | 说明 |",
        "|---|---:|---:|---|",
    ]
    for name, result in run["components"].items():
        lines.append(
            f"| {name} | {result['status']} | {result.get('duration_seconds', '-')} | "
            f"{result.get('reason', '')} |"
        )

    datasets = validation.get("datasets", [])
    if datasets:
        ds = datasets[0]
        lines += [
            "",
            "## 数据集",
            "",
            f"开发/消融集共 {ds['num_cases']} 条，其中可回答 {ds['answerable']} 条；"
            f"分布为 `{ds['distribution']}`。该集合没有独立标注，不能称为独立测试集。",
        ]

    dense = retrieval.get("groups", {}).get("Dense", {}).get("subsets", {}).get("overall", {})
    hybrid = retrieval.get("groups", {}).get("Dense+TF-IDF", {}).get("subsets", {}).get("overall", {})
    if dense and hybrid:
        retrieval_reproduced = run["components"].get("retrieval", {}).get("status") == "passed"
        lines += [
            "",
            "## 检索开发集消融（{}）".format("本次复现" if retrieval_reproduced else "结果文件快照"),
            "",
            "| 方案 | Recall@1 | Recall@3 | Recall@5 | MRR@3 |",
            "|---|---:|---:|---:|---:|",
            f"| Dense | {dense['recall@1']:.4f} | {dense['recall@3']:.4f} | {dense['recall@5']:.4f} | {dense['mrr@3']:.4f} |",
            f"| Dense + Char-TF-IDF | {hybrid['recall@1']:.4f} | {hybrid['recall@3']:.4f} | {hybrid['recall@5']:.4f} | {hybrid['mrr@3']:.4f} |",
            "",
            ("> 本次已在当前环境完成真实检索复测。"
             if retrieval_reproduced else
             "> 本次未重跑检索，上表只是结果文件快照，不代表已在当前环境复现。"),
        ]

    baseline = agentic.get("baseline", {})
    current = agentic.get("agentic_v5", {})
    if baseline and current:
        lines += [
            "",
            "## Agentic 决策逻辑消融（合成注入）",
            "",
            f"- Decision Accuracy：{baseline.get('decision_accuracy')} → {current.get('decision_accuracy')}"
            f"（n={agentic.get('num_cases')}）",
            f"- Unsafe Pass Rate：{baseline.get('unsafe_pass_rate')} → {current.get('unsafe_pass_rate')}",
        ]

    if safety:
        lines += [
            "",
            "## 安全故障注入（合成注入）",
            "",
            f"- 决策正确率：{safety.get('decision_correct')}（n={safety.get('num_cases')}）",
            f"- Unsafe Pass Rate：{safety.get('unsafe_pass_rate')}"
            f"（{safety.get('unsafe_pass_count')}/{safety.get('unsafe_pass_denominator')}）",
            f"- Safety Block Recall：{safety.get('safety_block_recall')}",
        ]

    struct_rows = [
        row for row in efficiency.get("struct_overhead", [])
        if not str(row.get("scenario", "")).startswith("real_")
    ]
    if struct_rows:
        latency = [row.get("latency_ms") for row in struct_rows if isinstance(row.get("latency_ms"), (int, float))]
        lines += [
            "",
            "## 编排微基准",
            "",
            f"- 确定性编排场景 n={len(struct_rows)}，延迟范围 "
            f"{min(latency):.2f}–{max(latency):.2f} ms。",
            "- 该数字默认不含真实 Dense 检索与 LLM 推理，不能作为端到端延迟。",
        ]

    tests = run["components"].get("tests", {})
    if tests.get("status"):
        lines += [
            "",
            "## 回归测试",
            "",
            f"- Agentic 核心与修复测试：{tests['status']}（23 + 33，共 56 项）。",
        ]

    lines += [
        "",
        "## 结论边界",
        "",
        "当前证据足以支持“完成检索消融、决策逻辑消融和安全故障注入”，"
        "不足以支持“达到临床可用准确率”。正式对外结果仍需冻结知识库和阈值后，"
        "使用未参与开发、由领域人员盲审的独立测试集复测。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--components",
        default="validation,agentic,safety,efficiency,retrieval",
        help="comma-separated: validation,agentic,safety,efficiency,retrieval,tests",
    )
    parser.add_argument("--real-efficiency", action="store_true")
    args = parser.parse_args()
    requested = [item.strip() for item in args.components.split(",") if item.strip()]
    valid = {"validation", "agentic", "safety", "efficiency", "retrieval", "tests"}
    unknown = sorted(set(requested) - valid)
    if unknown:
        parser.error(f"unknown components: {unknown}")

    manifest = load_json(MANIFEST_PATH)
    run = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": f"Python {platform.python_version()}",
        "requested_components": requested,
        "components": {},
    }
    scripts = {
        "validation": EVAL_DIR / "validate_evaluation_data.py",
        "agentic": EVAL_DIR / "eval_phase3_agentic.py",
        "safety": EVAL_DIR / "eval_phase3_safety.py",
        "efficiency": EVAL_DIR / "eval_phase3_efficiency.py",
        "retrieval": EVAL_DIR / "eval_phase3_retrieval.py",
    }
    for component in requested:
        if component == "retrieval":
            missing = [name for name in ("FlagEmbedding", "faiss") if not package_available(name)]
            if missing:
                run["components"][component] = {
                    "status": "skipped",
                    "reason": f"missing packages: {', '.join(missing)}; historical result retained",
                }
                continue
        if component == "tests":
            continue
        extra = ["--real"] if component == "efficiency" and args.real_efficiency else []
        run["components"][component] = run_script(scripts[component], extra)

    # Tests use unittest discovery and cannot be represented as a script path.
    if "tests" in requested:
        started = time.perf_counter()
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        test_outputs = []
        return_codes = []
        for test_file in ("tests/test_agentic_v5.py", "tests/test_agentic_fixes.py"):
            proc = subprocess.run(
                [sys.executable, test_file],
                cwd=ROOT_DIR,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1800,
            )
            return_codes.append(proc.returncode)
            test_outputs.append(f"## {test_file}\n{proc.stdout}\n{proc.stderr}")
        combined_output = "\n".join(test_outputs)
        run["components"]["tests"] = {
            "status": "passed" if all(code == 0 for code in return_codes) else "failed",
            "exit_code": max(return_codes),
            "duration_seconds": round(time.perf_counter() - started, 3),
            "stdout_tail": combined_output[-8000:],
            "stderr_tail": "",
        }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    RUN_RESULT.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(render_summary(run, manifest), encoding="utf-8")
    print(SUMMARY_PATH.read_text(encoding="utf-8"))
    failed = any(item["status"] == "failed" for item in run["components"].values())
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
