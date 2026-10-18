"""Launch the built local application on an available port and verify its HTTP surface."""

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "vtwin", "serve", "--port", str(port)], cwd=root
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            if process.poll() is not None:
                raise RuntimeError("Local application exited before becoming ready.")
            try:
                with urllib.request.urlopen(base + "/health", timeout=1) as response:
                    assert json.load(response)["status"] == "ok"
                break
            except (OSError, urllib.error.URLError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Local application did not become ready.") from None
                time.sleep(0.1)
        with urllib.request.urlopen(base, timeout=5) as response:
            assert "V-Twin workspace" in response.read().decode()
        with urllib.request.urlopen(base + "/api/v1/capabilities", timeout=5) as response:
            assert json.load(response)["simulation_available"] is False
        print("PASS: built UI, health and capability routes on the real local server.")
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    main()
