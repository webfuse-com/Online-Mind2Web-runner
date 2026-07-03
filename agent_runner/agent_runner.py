"""
Agent runner (collection step).

1. Pulls the Online-Mind2Web dataset from Hugging Face.
2. POST each dataset task to the agent (independent contexts).
3. Writes each response as a submission package:

<trajectories_dir>/<task_id>/result.json
<trajectories_dir>/<task_id>/trajectory/<nnnn>.png

{ schema_version, task, task_id, agent_final_answer, reference_length, action_history: [ { step, screenshot, url, action, action_status, thought }, ... ] }
`screenshot` may be a URL, data-URI, local path, or raw Base64.
"""


import argparse
import base64
import io
import json
import os
import shutil
import threading

from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from PIL import Image
from datasets import load_dataset
from dotenv import load_dotenv


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

    ap.add_argument("--agent-url", default=None)
    ap.add_argument("--agent-key", default=None)
    ap.add_argument("--agent-timeout", type=int, default=None)
    ap.add_argument("--resume", action="store_true")

    return ap.parse_args()


ARGS = _parse_args()
CFG = dict(
    # Dataset (via Hugging Face)
    hf_dataset=_env("HUGGINGFACE_DATASET", "osunlp/Online-Mind2Web"),
    hf_split=_env("HUGGINGFACE_SPLIT", "test"),
    hf_token=_env("HUGGINGFACE_TOKEN"),
    max_tasks=_env("MAX_TASKS", 0, int),
    # Runner
    num_workers=_env("NUM_WORKERS", 8, int),
    trajectories_dir=_env("TRAJECTORIES_DIR", os.path.join(HERE, "trajectories")),
)


_lock = threading.Lock()


def _screenshot_bytes(ref):
    if not ref:
        return None
    if isinstance(ref, str) and ref.startswith("data:"):
        raw = base64.b64decode(ref.split(",", 1)[1])
    elif isinstance(ref, str) and ref.startswith(("http://", "https://")):
        raw = requests.get(ref, timeout=60).content
    elif isinstance(ref, str) and os.path.exists(ref):
        with open(ref, "rb") as f:
            raw = f.read()
    else:
        raw = base64.b64decode(ref)

    img = Image.open(io.BytesIO(raw))

    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()

    img.save(buf, format="PNG")

    return buf.getvalue()


def call_agent(task):
    # POST the task + start URL to the agent; expect a v2 result object back.
    headers = {"Content-Type": "application/json"}

    if ARGS.agent_key:
        headers["Authorization"] = f"Bearer {ARGS.agent_key}"

    body = {
        "task_id": task["task_id"],
        "task": task["confirmed_task"],
        "website": task["website"],
        "start_url": task["website"],   # alias
        "reference_length": task["reference_length"],
    }

    r = requests.post(ARGS.agent_url, headers=headers, json=body, timeout=ARGS.agent_timeout)
    r.raise_for_status()

    return r.json()

def build_package(task, result):
    tid = task["task_id"]
    tdir = os.path.join(CFG["trajectories_dir"], tid)
    traj = os.path.join(tdir, "trajectory")

    os.makedirs(traj, exist_ok=True)

    result = dict(result)
    result.setdefault("schema_version", "online-mind2web-v2")
    result.setdefault("task", task["confirmed_task"])
    result["task_id"] = tid
    result.setdefault("reference_length", task["reference_length"])

    steps = result.get("action_history", [])

    if not steps:
        raise ValueError("agent returned an empty action_history")

    if isinstance(steps[0], dict):  # v2
        for i, step in enumerate(steps):
            fname = f"{i:04d}.png"
            img = _screenshot_bytes(step.get("screenshot"))

            if img is not None:
                with open(os.path.join(traj, fname), "wb") as f:
                    f.write(img)

            step["screenshot"] = fname
            step.setdefault("step", i)
            step.setdefault("thought", None)
    else:  # tolerate v1
        shots = result.get("screenshots", [])

        for i, img_ref in enumerate(shots):
            img = _screenshot_bytes(img_ref)

            if img is not None:
                with open(os.path.join(traj, f"{i:04d}.png"), "wb") as f:
                    f.write(img)

    with open(os.path.join(tdir, "result.json"), "w") as f:
        json.dump(result, f)
    return tdir

def collect_task(task):
    tid = task["task_id"]
    tdir = os.path.join(CFG["trajectories_dir"], tid)

    if os.path.exists(os.path.join(tdir, "result.json")):
        return tid, None

    try:
        result = call_agent(task)
        build_package(task, result)
        with _lock:
            print(f"[collect] {tid} ok")

        return tid, None
    except Exception as e:
        with _lock:
            print(f"[collect] {tid} FAILED: {e}")

        return tid, str(e)

def check_agent_reachable():
    try:
        requests.get(ARGS.agent_url, timeout=10)
    except requests.exceptions.RequestException as e:
        raise SystemExit(f"Agent at {ARGS.agent_url} is not reachable: {e}")

def run():
    check_agent_reachable()

    if not ARGS.resume:
        shutil.rmtree(CFG["trajectories_dir"], ignore_errors=True)

    ds = load_dataset(CFG["hf_dataset"], split=CFG["hf_split"], token=CFG["hf_token"])
    tasks = list(ds)

    if CFG["max_tasks"]:
        tasks = tasks[: CFG["max_tasks"]]

    os.makedirs(CFG["trajectories_dir"], exist_ok=True)

    print(f"Collecting {len(tasks)} trajectories from agent (workers={CFG['num_workers']}) ...")

    ok, failed = 0, []

    with ThreadPoolExecutor(max_workers=CFG["num_workers"]) as pool:
        futs = [pool.submit(collect_task, t) for t in tasks]

        for fut in as_completed(futs):
            tid, err = fut.result()

            if err:
                failed.append((tid, err))
            else:
                ok += 1

    print(f"\nCollected {ok} trajectories; {len(failed)} agent failures.")

    if failed:
        for tid, err in failed[:10]:
            print(f"  - {tid}: {err}")

    n_pkgs = sum(
        1 for d in os.listdir(CFG["trajectories_dir"])
        if os.path.exists(os.path.join(CFG["trajectories_dir"], d, "result.json"))
    )

    print(f"Trajectories directory now has {n_pkgs} package(s): {CFG['trajectories_dir']}")

    if n_pkgs == 0:
        raise SystemExit("No trajectories collected.")