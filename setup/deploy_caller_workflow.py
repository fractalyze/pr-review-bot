# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Deploy the caller workflow to all repos in the fractalyze org."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

API_BASE = "https://api.github.com"
ORG = "fractalyze"
WORKFLOW_PATH = ".github/workflows/pr-review-notify.yml"
TEMPLATE = Path(__file__).parent / "caller_workflow_template.yml"
SKIP_REPOS = {"pr-review-bot", ".github"}


def _token() -> str:
    token = os.environ.get("GH_PAT", "")
    if not token:
        raise RuntimeError("GH_PAT environment variable is not set")
    return token


def _request(method: str, path: str, body: dict | None = None) -> dict | None:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def _list_repos() -> list[str]:
    repos: list[str] = []
    page = 1
    while True:
        result = _request("GET", f"/orgs/{ORG}/repos?type=all&per_page=100&page={page}")
        if not result:
            break
        repos.extend(r["name"] for r in result if r["name"] not in SKIP_REPOS)
        if len(result) < 100:
            break
        page += 1
    return repos


def _file_exists(repo: str) -> str | None:
    """Check if the workflow file already exists. Returns its SHA if it does."""
    result = _request("GET", f"/repos/{ORG}/{repo}/contents/{WORKFLOW_PATH}")
    if result and "sha" in result:
        return result["sha"]
    return None


def _deploy(repo: str, content: str, dry_run: bool) -> None:
    existing_sha = _file_exists(repo)
    if existing_sha:
        print(f"  SKIP {repo} (already exists)")
        return

    if dry_run:
        print(f"  DRY-RUN {repo} (would create {WORKFLOW_PATH})")
        return

    encoded = base64.b64encode(content.encode()).decode()
    _request(
        "PUT",
        f"/repos/{ORG}/{repo}/contents/{WORKFLOW_PATH}",
        {
            "message": "ci: add PR review notification workflow",
            "content": encoded,
            "branch": "main",
        },
    )
    print(f"  DEPLOYED {repo}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy caller workflow to org repos")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deploying")
    args = parser.parse_args()

    content = TEMPLATE.read_text()
    repos = _list_repos()
    print(f"Found {len(repos)} repos in {ORG} (excluding {SKIP_REPOS})\n")

    for repo in sorted(repos):
        _deploy(repo, content, args.dry_run)

    print("\nDone.")


if __name__ == "__main__":
    main()
