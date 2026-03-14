# Copyright 2026 Fractalyze Inc. All rights reserved.

"""GitHub REST API client using urllib (no external dependencies)."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any

API_BASE = "https://api.github.com"


def _token() -> str:
    token = os.environ.get("GH_PAT", "")
    if not token:
        raise RuntimeError("GH_PAT environment variable is not set")
    return token


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
) -> Any:
    """Make an authenticated GitHub API request."""
    url = f"{API_BASE}{path}" if path.startswith("/") else path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {_token()}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if data:
        req.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())


def _get(path: str) -> Any:
    return _request("GET", path)


def _paginate(path: str) -> list[Any]:
    """Fetch all pages from a paginated GitHub API endpoint."""
    results: list[Any] = []
    separator = "&" if "?" in path else "?"
    url = f"{API_BASE}{path}{separator}per_page=100"

    while url:
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {_token()}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")

        with urllib.request.urlopen(req) as resp:
            results.extend(json.loads(resp.read().decode()))
            link = resp.headers.get("Link", "")
            url = _parse_next_link(link)

    return results


def _parse_next_link(link_header: str) -> str | None:
    """Extract the 'next' URL from a GitHub Link header."""
    for part in link_header.split(","):
        if 'rel="next"' in part:
            start = part.index("<") + 1
            end = part.index(">")
            return part[start:end]
    return None


def list_open_prs(owner: str, repo: str) -> list[dict[str, Any]]:
    """List open pull requests for a repository."""
    return _paginate(f"/repos/{owner}/{repo}/pulls?state=open")


def get_requested_reviewers(
    owner: str, repo: str, pr_number: int
) -> dict[str, Any]:
    """Get requested reviewers (users and teams) for a pull request."""
    return _get(f"/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers")


def get_pr(owner: str, repo: str, pr_number: int) -> dict[str, Any]:
    """Get a single pull request."""
    return _get(f"/repos/{owner}/{repo}/pulls/{pr_number}")


def get_ready_for_review_at(
    owner: str, repo: str, pr_number: int
) -> str | None:
    """Return the timestamp when a PR was marked ready for review.

    Uses the timeline API to find the ``ready_for_review`` event.
    Returns ``None`` if the PR was never a draft.
    """
    events = _paginate(
        f"/repos/{owner}/{repo}/issues/{pr_number}/timeline"
    )
    ready_at = None
    for event in events:
        if event.get("event") == "ready_for_review":
            ready_at = event.get("created_at")
    return ready_at


def get_user_info(login: str) -> dict[str, Any]:
    """Get public user profile information."""
    return _get(f"/users/{login}")
