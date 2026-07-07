import argparse
import glob
import json
import os
import statistics

from dotenv import load_dotenv


PKG_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(PKG_DIR)

load_dotenv(os.path.join(HERE, ".env"))

EVAL_MODE = "WebJudge_Online_Mind2Web_eval"

def _parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument("path", nargs="?", default=None, help="Path to the upstream auto_eval_results.json (JSONL).")
    ap.add_argument("--json", action="store_true", help="Print metrics as JSON instead of a text report.")
    ap.add_argument("--verbose", action="store_true", help="List failed task_ids with their reason.")
    ap.add_argument("--out", default=None, help="Also write the output to this file.")

    return ap.parse_args()

ARGS = _parse_args()


def _env(key, default=None, cast=str):
    val = os.getenv(key)
    return cast(val) if val else default


def default_results_path():
    output_path = _env("OUTPUT_PATH", os.path.join(HERE, "judge_result"))
    judge_llm = _env("JUDGE_LLM", "gpt-4o")
    score_threshold = _env("SCORE_THRESHOLD", 3, int)

    fname = f"{EVAL_MODE}_{judge_llm}_score_threshold_{score_threshold}_auto_eval_results.json"
    path = os.path.join(output_path, fname)

    if os.path.exists(path):
        return path

    matches = sorted(glob.glob(os.path.join(output_path, "*_auto_eval_results.json")),
                      key=os.path.getmtime, reverse=True)
    return matches[0] if matches else path


def load_results(path):
    records = []

    with open(path) as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    return records


def _failure_reason(record):
    resp = record.get("evaluation_details", {}).get("response", "")
    reason = resp.split("Status:")[0].replace("Thoughts:", "").strip()

    return reason[:160]


def compute_metrics(records):
    n = len(records)

    if n == 0:
        return {"total": 0}

    labels = [int(r.get("predicted_label", 0)) for r in records]
    successes = sum(labels)

    image_scores = [
        img.get("Score") for r in records
        for img in r.get("image_judge_record", [])
        if isinstance(img.get("Score"), (int, float))
    ]

    steps = [len(r.get("action_history", [])) for r in records]
    ref_lengths = [r.get("reference_length") for r in records if r.get("reference_length")]

    failed = [
        {"task_id": r.get("task_id"), "reason": _failure_reason(r)}
        for r, label in zip(records, labels) if label == 0
    ]

    return {
        "total": n,
        "successes": successes,
        "failures": n - successes,
        "success_rate": 100.0 * successes / n,
        "avg_image_judge_score": statistics.mean(image_scores) if image_scores else None,
        "avg_steps_taken": statistics.mean(steps) if steps else None,
        "avg_reference_length": statistics.mean(ref_lengths) if ref_lengths else None,
        "failed": failed,
    }


def format_report(metrics, path, verbose=False):
    if metrics["total"] == 0:
        return f"No records found in {path}"

    lines = [
        f"Results: {path}",
        f"Total tasks:\t\t\t{metrics['total']}",
        f"Successes:\t\t\t{metrics['successes']}",
        f"Failures:\t\t\t{metrics['failures']}",
        f"Success rate:\t\t\t{metrics['success_rate']:.1f}%",
    ]

    if metrics["avg_image_judge_score"] is not None:
        lines.append(f"Avg image judge score:\t\t{metrics['avg_image_judge_score']:.2f} / 5")

    if metrics["avg_steps_taken"] is not None:
        lines.append(f"Avg steps taken:\t\t{metrics['avg_steps_taken']:.1f}")

    if metrics["avg_reference_length"] is not None:
        lines.append(f"Avg steps length (reference):\t{metrics['avg_reference_length']:.1f}")

    if verbose and metrics["failed"]:
        lines.append("\nFailed tasks:")

        for f in metrics["failed"]:
            lines.append(f"  - {f['task_id']}: {f['reason']}")

    return "\n".join(lines)



def run():
    path = ARGS.path or default_results_path()

    if not os.path.exists(path):
        raise SystemExit(f"No results file at {path}")

    metrics = compute_metrics(load_results(path))
    output = json.dumps(metrics, indent=2) if ARGS.json else format_report(metrics, path, verbose=ARGS.verbose)

    print(output)

    if ARGS.out:
        with open(ARGS.out, "w") as f:
            f.write(output + "\n")