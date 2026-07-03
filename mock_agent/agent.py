import argparse
import base64
import contextlib
import io
import json
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw


class Handler(BaseHTTPRequestHandler):
    quiet = False

    def log_message(self, *a):
        pass

    def do_GET(self): # health check
        self._send(200, {
            "status": "ok",
            "agent": "mock",
        })

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:  # noqa: BLE001
            return self._send(400, {"error": f"bad request: {e}"})

        if not self.quiet:
            print(f"[mock] task_id={req.get('task_id')} website={req.get('website')}")

        self._send(200, build_result(req))

    def _send(self, code, obj):
        body = json.dumps(obj).encode()

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _screenshot(lines):
    img = Image.new("RGB", (640, 360), (245, 245, 248))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 639, 36], fill=(40, 90, 160))
    y = 56

    for ln in lines:
        draw.text((16, y), ln[:90], fill=(20, 20, 20))
        y += 22

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

def _wait_ready(url, timeout=10.0):
    deadline = time.time() + timeout
    health = url.rsplit("/agent", 1)[0] + "/"

    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=1) as r:
                if r.status == 200:
                    return
        except Exception:  # noqa: BLE001
            time.sleep(0.1)

    raise RuntimeError(f"Mock agent did not become ready at {health}")


def build_result(req):
    task = req.get("task", "")
    start = req.get("website") or req.get("start_url") or "https://example.com"
    answer = f"Completed (mock): {task}"
    steps = [
        {
            "action": "page -> NAVIGATE -> open start page | SUCCESS",
            "thought": "Navigating to the provided start URL.",
            "url": start,
            "shot": [ "MOCK BROWSER", f"NAVIGATE {start}", task ]
        },
        {
            "action": "CLICK coords(320, 180) -> click primary result | SUCCESS",
            "thought": "Clicking the most relevant element for the task.", "url": start,
            "shot": [ "MOCK BROWSER", "CLICK (320,180)", task ]
        },
        {
            "action": f"TASK_COMPLETE -> ANSWER: {answer}",
            "thought": "Task appears complete; reporting the answer.", "url": start,
            "shot": [ "MOCK BROWSER", "TASK COMPLETE", answer ]
        },
    ]

    return {
        "schema_version": "online-mind2web-v2",
        "task": task,
        "task_id": req.get("task_id", "mock"),
        "agent_final_answer": answer,
        "reference_length": req.get("reference_length", len(steps)),
        "action_history": [
            {
                "step": i,
                "screenshot": _screenshot(s["shot"]),
                "url": s["url"],
                "action": s["action"],
                "action_status": None,
                "thought": s["thought"]
            } for i, s in enumerate(steps)
        ],
    }

def make_server(host="127.0.0.1", port=8000, quiet=False):
    handler = type("H", (Handler,), {"quiet": quiet})

    return ThreadingHTTPServer((host, port), handler)

def run():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--quiet", action="store_true")

    args = ap.parse_args()
    srv = make_server(args.host, args.port, quiet=args.quiet)

    print(f"Mock agent on http://{args.host}:{args.port}/agent")

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass