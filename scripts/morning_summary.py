# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Morning summary: scan all org repos and post channel summary."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from scripts import github_client, slack_client, user_mapper, format_slack

ORG = "fractalyze"
CONFIG_PATH = Path(__file__).parent.parent / "config.yml"


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
        print("WARNING: no repos configured", file=sys.stderr)
    return repos


def _collect_pending_reviews() -> dict[str, list[dict]]:
    """Scan whitelisted repos and collect pending review information.

    Returns:
        pending_by_repo: {repo_full_name: [pr_info, ...]}
    """
    pending_by_repo: dict[str, list[dict]] = defaultdict(list)

    repo_names = _load_repo_whitelist()
    print(f"Scanning {len(repo_names)} whitelisted repositories in {ORG}...")

    for name in repo_names:
        repo_name = f"{ORG}/{name}"
        owner = ORG

        try:
            prs = github_client.list_open_prs(owner, name)
        except Exception as e:
            print(f"WARNING: failed to list PRs for {repo_name}: {e}", file=sys.stderr)
            continue

        for pr in prs:
            if pr.get("draft"):
                continue

            try:
                reviewer_data = github_client.get_requested_reviewers(
                    owner, name, pr["number"]
                )
            except Exception as e:
                print(
                    f"WARNING: failed to get reviewers for {repo_name}#{pr['number']}: {e}",
                    file=sys.stderr,
                )
                continue

            reviewer_logins = [u["login"] for u in reviewer_data.get("users", [])]
            if not reviewer_logins:
                continue

            pending_by_repo[repo_name].append({
                "number": pr["number"],
                "title": pr["title"],
                "url": pr["html_url"],
                "author": pr["user"]["login"],
                "created_at": pr["created_at"],
                "reviewers": reviewer_logins,
            })

    return dict(pending_by_repo)


def _build_slack_map(
    pending_by_repo: dict[str, list[dict]],
) -> dict[str, str | None]:
    """Resolve all GitHub logins (authors + reviewers) to Slack user IDs."""
    logins: set[str] = set()
    for prs in pending_by_repo.values():
        for pr in prs:
            logins.add(pr["author"])
            logins.update(pr["reviewers"])
    return {login: user_mapper.resolve(login) for login in logins}


def _send_channel_summary(
    pending_by_repo: dict[str, list[dict]],
    slack_map: dict[str, str | None],
) -> None:
    """Post the summary table to the #pr-reviews channel."""
    channel_id = os.environ.get("SLACK_SUMMARY_CHANNEL_ID", "")
    if not channel_id:
        print("WARNING: SLACK_SUMMARY_CHANNEL_ID not set, skipping channel summary", file=sys.stderr)
        return

    blocks = format_slack.channel_summary_blocks(pending_by_repo, slack_map)
    total = sum(len(prs) for prs in pending_by_repo.values())
    slack_client.post_message(
        channel_id,
        blocks,
        text=f"PR Review Summary: {total} PRs pending",
    )
    print(f"Posted channel summary: {total} PRs across {len(pending_by_repo)} repos")


def main() -> None:
    pending_by_repo = _collect_pending_reviews()

    if not pending_by_repo:
        print("No pending reviews found. Nothing to send.")
        return

    slack_map = _build_slack_map(pending_by_repo)
    _send_channel_summary(pending_by_repo, slack_map)

    print("Morning summary complete.")


if __name__ == "__main__":
    main()
