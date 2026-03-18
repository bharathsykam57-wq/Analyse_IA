"""Smoke test for DVC bootstrap script in dry-run mode."""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "scripts", "bootstrap_dvc.sh")

    if not os.path.exists(script):
        print("FAIL: bootstrap_dvc.sh not found")
        return 1

    proc = subprocess.run(
        ["bash", script, "--dry-run"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )

    if proc.returncode != 0:
        print("FAIL: dry-run exited non-zero")
        print(proc.stdout)
        print(proc.stderr)
        return 1

    output = proc.stdout + "\n" + proc.stderr
    required_snippets = [
        "DVC BOOTSTRAP",
        "[DRY-RUN] dvc init",
        "PASS: DVC bootstrap completed",
    ]

    missing = [snippet for snippet in required_snippets if snippet not in output]
    if missing:
        print("FAIL: expected output snippets missing")
        for snippet in missing:
            print(f"  - {snippet}")
        print(output)
        return 1

    print("PASS: DVC bootstrap dry-run smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
