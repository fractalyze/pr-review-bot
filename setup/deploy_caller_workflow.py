# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Deploy the caller workflow to whitelisted repos in the fractalyze org."""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

import yaml

API_BASE = "https://api.github.com"
ORG = "fractalyze"
WORKFLOW_PATH = ".github/workflows/pr-review-notify.yml"
TEMPLATE = Path(__file__).parent / "caller_workflow_template.yml"
CONFIG_PATH = Path(__file__).parent.parent / "config.yml"


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


def _load_repo_whitelist() -> list[str]:
    """Load whitelisted repo names from env var or config.yml."""
    env_repos = os.environ.get("MONITORED_REPOS", "")
    if env_repos:
        return [r.strip() for r in env_repos.split(",") if r.strip()]

    if not CONFIG_PATH.exists():
        raise RuntimeError(
            "MONITORED_REPOS env var not set and config file not found"
        )
    with open(CONFIG_PATH) as f:
        config = yaml.safe_load(f)
    repos = config.get("repos") or []
    if not repos:
        raise RuntimeError("No repos configured")
    return repos


def _file_exists(repo: str) -> str | None:
    """Check if the workflow file already exists. Returns its SHA if it does."""
    result = _request("GET", f"/repos/{ORG}/{repo}/contents/{WORKFLOW_PATH}")
    if result and "sha" in result:
        return result["sha"]
    return None


def _deploy(repo: str, content: str, *, dry_run: bool, force: bool) -> None:
    existing_sha = _file_exists(repo)
    if existing_sha and not force:
        print(f"  SKIP {repo} (already exists, use --force to update)")
        return

    action = "update" if existing_sha else "create"
    if dry_run:
        print(f"  DRY-RUN {repo} (would {action} {WORKFLOW_PATH})")
        return

    encoded = base64.b64encode(content.encode()).decode()
    body: dict = {
        "message": f"ci: {action} PR review notification workflow",
        "content": encoded,
        "branch": "main",
    }
    if existing_sha:
        body["sha"] = existing_sha

    _request("PUT", f"/repos/{ORG}/{repo}/contents/{WORKFLOW_PATH}", body)
    print(f"  {'UPDATED' if existing_sha else 'DEPLOYED'} {repo}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy caller workflow to org repos")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deploying")
    parser.add_argument("--force", action="store_true", help="Update existing workflow files")
    args = parser.parse_args()

    content = TEMPLATE.read_text()
    repos = _load_repo_whitelist()
    print(f"Deploying to {len(repos)} whitelisted repos in {ORG}\n")

    for repo in sorted(repos):
        _deploy(repo, content, dry_run=args.dry_run, force=args.force)

    print("\nDone.")


if __name__ == "__main__":
    main()
