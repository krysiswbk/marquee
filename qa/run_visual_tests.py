"""Run every browser visual check, including script-only and pytest-only cases.

Usage: MARQUEE_CHROMIUM=/path/to/chrome python qa/run_visual_tests.py
"""

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"


def run_case(label: str, command: list[str], timeout: int, env: dict[str, str]) -> bool:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        print(f"FAIL {label} (timeout after {timeout}s)", flush=True)
        if error.stdout:
            output = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout
            print(output[-3000:], flush=True)
        return False
    status = "PASS" if result.returncode == 0 else f"FAIL (exit {result.returncode})"
    print(f"{status} {label}", flush=True)
    if result.returncode:
        print(result.stdout[-6000:], flush=True)
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=360, help="seconds per invocation")
    parser.add_argument("--filter", default="", help="substring of browser test filename")
    args = parser.parse_args()
    files = sorted(path for path in TESTS.glob("browser_*.py") if args.filter in path.name)
    if not files:
        parser.error("no browser tests matched")
    chromium = os.environ.get("MARQUEE_CHROMIUM", "")
    if not chromium or not Path(chromium).is_file() or not os.access(chromium, os.X_OK):
        parser.error("set MARQUEE_CHROMIUM to an executable Chromium path")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env.update({
        "MARQUEE_SMOKE_URL": base,
        "MARQUEE_BASE_URL": base,
        "MARQUEE_CHROMIUM": chromium,
        "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
    })
    results = []
    with tempfile.TemporaryDirectory(prefix="marquee-visual-") as data_dir:
        (Path(data_dir) / "marquee.json").write_text(json.dumps({"attention": {
            "signal_bindings": [{"entity_id": "binary_sensor.test_leak", "category": "leak"}],
            "rules": [{"id": "test_leak", "match": {"category": "leak"},
                       "title": "Test leak detected", "active_state": "on",
                       "acknowledgement_required": True,
                       "escalation": [{"id": "critical", "urgency": "CRITICAL", "priority": 100}]}],
        }}))
        server_env = env.copy()
        for key in tuple(server_env):
            if key.startswith(("PLEX_", "EMBY_", "JELLYFIN_", "HA_", "TMDB_", "HUB_")) or key.endswith("_HUB_IP"):
                server_env.pop(key)
        server_env.update({
            "REPO_DIR": str(ROOT), "DATA_DIR": data_dir, "SERVE_PORT": str(port),
            "PAGE_URL": base + "/image", "POLL_SECONDS": "999", "HUB_IP": "",
            "GARAGE_HUB_IP": "", "BEDROOM_HUB_IP": "",
        })
        with (Path(data_dir) / "server.log").open("w") as server_log:
            server = subprocess.Popen(
                [sys.executable, "cast/cast.py"], cwd=ROOT, env=server_env,
                stdout=server_log, stderr=subprocess.STDOUT,
            )
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if server.poll() is not None:
                        raise RuntimeError("isolated Marquee app exited during startup")
                    try:
                        with urllib.request.urlopen(base + "/healthz", timeout=1) as response:
                            if response.status == 200:
                                break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.2)
                else:
                    raise RuntimeError("isolated Marquee app did not become healthy")
                for path in files:
                    relative = path.relative_to(ROOT).as_posix()
                    results.append((relative, run_case(relative, [sys.executable, str(path)], args.timeout, env)))
                    source = path.read_text()
                    if re.search(r"^\s*(?:async\s+)?def\s+test_", source, re.MULTILINE):
                        label = f"pytest {relative}"
                        command = [sys.executable, "-m", "pytest", "-q", relative]
                        results.append((label, run_case(label, command, args.timeout, env)))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
    failures = [name for name, passed in results if not passed]
    print(f"Visual suite: {len(results) - len(failures)}/{len(results)} invocations passed", flush=True)
    if failures:
        print("Failed: " + ", ".join(failures), flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
