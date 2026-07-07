"""
Judge runner (evaluation step).
Reads submission packages from trajectories_dir:
<trajectories_dir>/<task_id>/result.json
<trajectories_dir>/<task_id>/trajectory/<nnnn>.png
Writes the results to the results_dir:
judge_results/ (default)
Invokes the WebJudge_Online_Mind2Web_eval evaluator as-is.
"""


import argparse
import json
import os
import shutil
import subprocess
import sys

from dotenv import load_dotenv


EVAL_MODE = "WebJudge_Online_Mind2Web_eval"
PKG_DIR = os.path.dirname(os.path.abspath(__file__))
HERE = os.path.dirname(PKG_DIR)

load_dotenv(os.path.join(HERE, ".env"))


def _env(key, default=None, cast=str, required=False):
    val = os.getenv(key)

    if val is None or val == "":
        if required:
            raise SystemExit(f"Missing required env var: {key}")

        return default

    return cast(val)

def _parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument("--trajectories", default="./trajectories")
    ap.add_argument("--resume", action="store_true")

    return ap.parse_args()


ARGS = _parse_args()
CFG = dict(
    submodule_dir=_env("SUBMODULE_DIR", os.path.join(HERE, "third_party", "Online-Mind2Web")),
    judge_llm=_env("JUDGE_LLM", "gpt-4o"),
    judge_llm_api_key=_env("JUDGE_LLM_API_KEY", required=True),
    score_threshold=_env("SCORE_THRESHOLD", 3, int),
    eval_workers=_env("EVAL_WORKERS", 8, int),
    output_path=_env("OUTPUT_PATH", os.path.join(HERE, "judge_result")),
)


def count_packages():
    if not os.path.isdir(ARGS.trajectories):
        return 0

    return sum(
        1 for d in os.listdir(ARGS.trajectories)
        if os.path.exists(os.path.join(ARGS.trajectories, d, "result.json"))
    )


def run_upstream_eval(num_tasks):
    run_py = os.path.join(CFG["submodule_dir"], "src", "run.py")

    if not os.path.exists(run_py):
        raise SystemExit(
            f"Submodule not found at {CFG['submodule_dir']}. Run ./setup_submodule.sh first.")

    nw = max(1, min(CFG["eval_workers"], max(1, num_tasks)))

    cmd = [
        sys.executable, run_py,
        "--mode", EVAL_MODE,
        "--model", CFG["judge_llm"],
        "--trajectories_dir", ARGS.trajectories,
        "--api_key", CFG["judge_llm_api_key"],
        "--output_path", CFG["output_path"],
        "--score_threshold", str(CFG["score_threshold"]),
        "--num_worker", str(nw),
    ]
    safe = [("***" if cmd[i - 1] == "--api_key" else c) for i, c in enumerate(cmd)]

    print(f"\n[judge] invoking upstream WebJudge as-is:\n  {' '.join(safe)}\n")

    subprocess.run(cmd, check=True)

def summarize():
    fname = (f"{EVAL_MODE}_{CFG['judge_llm']}_score_threshold_{CFG['score_threshold']}_auto_eval_results.json")
    path = os.path.join(CFG["output_path"], fname)

    if not os.path.exists(path):
        print(f"[warn] no upstream results file at {path}")

        return

    labels = []

    with open(path) as f:
        for line in f:
            try:
                labels.append(int(json.loads(line)["predicted_label"]))
            except Exception:  # noqa: BLE001
                pass

    if labels:
        print(f"\nWebJudge success rate: {100.0 * sum(labels) / len(labels):.1f}% "
              f"({sum(labels)}/{len(labels)})")
        print(f"Per-task details: {path}")

def run():
    n_pkgs = count_packages()

    if n_pkgs == 0:
        raise SystemExit(
            f"No trajectories found in {ARGS.trajectories}. Run agent_runner first.")

    if not ARGS.resume:
        shutil.rmtree(CFG["output_path"], ignore_errors=True)

    run_upstream_eval(n_pkgs)
    summarize()