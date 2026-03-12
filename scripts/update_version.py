#!/usr/bin/env python3
"""Check for new rtk releases and update setup.py.

When run in GitHub Actions (GITHUB_ACTIONS=true), this script also creates
a branch, commits the change, tags it, and pushes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = "rtk-ai/rtk"

ARCHIVE_TARGETS = [
    "rtk-x86_64-unknown-linux-musl.tar.gz",
    "rtk-aarch64-unknown-linux-gnu.tar.gz",
    "rtk-x86_64-apple-darwin.tar.gz",
    "rtk-aarch64-apple-darwin.tar.gz",
    "rtk-x86_64-pc-windows-msvc.zip",
]

ROOT = Path(__file__).resolve().parent.parent
SETUP_PY = ROOT / "setup.py"


def get_current_version() -> str:
    text = SETUP_PY.read_text()
    match = re.search(r"RTK_VERSION\s*=\s*'([^']+)'", text)
    if not match:
        raise RuntimeError("Could not find RTK_VERSION in setup.py")
    return match.group(1)


def get_py_version() -> str:
    text = SETUP_PY.read_text()
    match = re.search(r"PY_VERSION\s*=\s*'([^']+)'", text)
    if not match:
        raise RuntimeError("Could not find PY_VERSION in setup.py")
    return match.group(1)


def get_latest_release() -> tuple[str, dict[str, str]]:
    """Return (version, {filename: sha256}) for the latest GitHub release."""
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read())

    tag = data["tag_name"].lstrip("v")

    checksums_url = next(
        a["browser_download_url"]
        for a in data["assets"]
        if a["name"] == "checksums.txt"
    )

    with urllib.request.urlopen(checksums_url) as resp:
        checksums_text = resp.read().decode()

    hashes: dict[str, str] = {}
    for line in checksums_text.strip().splitlines():
        sha256, filename = line.split(None, 1)
        hashes[filename.strip()] = sha256.strip()

    return tag, hashes


def update_setup_py(new_version: str, hashes: dict[str, str]) -> None:
    text = SETUP_PY.read_text()

    text = re.sub(
        r"RTK_VERSION\s*=\s*'[^']+'",
        f"RTK_VERSION = '{new_version}'",
        text,
    )
    text = re.sub(
        r"PY_VERSION\s*=\s*'[^']+'",
        "PY_VERSION = '1'",
        text,
    )

    for archive_name in ARCHIVE_TARGETS:
        sha = hashes.get(archive_name)
        if not sha:
            raise RuntimeError(f"Missing checksum for {archive_name} in release")

        target = archive_name.removeprefix("rtk-")
        for suffix in (".tar.gz", ".zip"):
            target = target.removesuffix(suffix)

        pattern = re.compile(rf'("{re.escape(target)}":\s*")[0-9a-f]{{64}}(")')
        text, count = pattern.subn(rf"\g<1>{sha}\2", text)
        if count == 0:
            raise RuntimeError(f"Could not find hash slot for target {target}")

    SETUP_PY.write_text(text)


def git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True)


def commit_and_push(rtk_version: str, full_version: str) -> None:
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    git("add", "setup.py")
    git("commit", "-m", f"Update rtk to v{rtk_version}")
    git("tag", f"v{full_version}")
    git("push", "origin", "main", f"v{full_version}")


def main() -> int:
    current = get_current_version()
    print(f"Current RTK_VERSION: {current}")

    latest, hashes = get_latest_release()
    print(f"Latest release:      {latest}")

    if current == latest:
        print("Already up to date.")
        return 0

    print(f"Updating {current} -> {latest}")
    update_setup_py(latest, hashes)

    py_version = get_py_version()
    full_version = f"{latest}.{py_version}"
    print(f"  setup.py updated (full version: {full_version})")

    if os.environ.get("GITHUB_ACTIONS") == "true":
        print("Running in CI — committing and pushing...")
        commit_and_push(latest, full_version)
        print(f"Pushed to main and tagged v{full_version}")

        output_file = os.environ.get("GITHUB_OUTPUT")
        if output_file:
            with open(output_file, "a") as f:
                f.write(f"tag=v{full_version}\n")
    else:
        print("Not in CI — skipping git commit/push.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
