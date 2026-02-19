# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Morning summary: scan all org repos and send DMs + channel summary."""

from __future__ import annotations

import os
import sys
from collections import defaultdict

from scripts import github_client, slack_client, user_mapper, format_slack

ORG = "fractalyze"


def _collect_pending_reviews() -> (
    tuple[dict[str, list[dict]], dict[str, list[dict]]]
):
    """Scan all org repos and collect pending review information.

    Returns:
        (pending_by_repo, pending_by_reviewer)
        - pending_by_repo: {repo_full_name: [pr_info, ...]}
        - pending_by_reviewer: {github_login: [pr_info, ...]}
    """
    pending_by_repo: dict[str, list[dict]] = defaultdict(list)
    pending_by_reviewer: dict[str, list[dict]] = defaultdict(list)

    repos = github_client.list_org_repos(ORG)
    print(f"Scanning {len(repos)} repositories in {ORG}...")

    for repo in repos:
        repo_name = repo["full_name"]
        owner, name = repo_name.split("/")

        try:
            prs = github_client.list_open_prs(owner, name)
        except Exception as e:
            print(f"WARNING: failed to list PRs for {repo_name}: {e}", file=sys.stderr)
            continue

        for pr in prs:
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

            pr_info = {
                "number": pr["number"],
                "title": pr["title"],
                "url": pr["html_url"],
                "author": pr["user"]["login"],
                "created_at": pr["created_at"],
                "reviewers": reviewer_logins,
            }

            pending_by_repo[repo_name].append(pr_info)
            for login in reviewer_logins:
                pending_by_reviewer[login].append(
                    {**pr_info, "repo": repo_name}
                )

    return dict(pending_by_repo), dict(pending_by_reviewer)


def _send_individual_dms(
    pending_by_reviewer: dict[str, list[dict]],
) -> dict[str, str | None]:
    """Send morning DMs to each reviewer. Returns the slack_map used."""
    slack_map: dict[str, str | None] = {}

    for login, prs in pending_by_reviewer.items():
        slack_id = user_mapper.resolve(login)
        slack_map[login] = slack_id

        if slack_id is None:
            continue

        prs_by_repo: dict[str, list[dict]] = defaultdict(list)
        for pr in prs:
            prs_by_repo[pr["repo"]].append(pr)

        blocks = format_slack.individual_dm_blocks(login, dict(prs_by_repo))
        try:
            slack_client.send_dm(slack_id, blocks, text=f"You have {len(prs)} PRs awaiting review")
            print(f"Sent DM to {login} ({slack_id}): {len(prs)} PRs")
        except Exception as e:
            print(f"WARNING: failed to send DM to {login}: {e}", file=sys.stderr)

    return slack_map


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
    pending_by_repo, pending_by_reviewer = _collect_pending_reviews()

    if not pending_by_reviewer:
        print("No pending reviews found. Nothing to send.")
        return

    slack_map = _send_individual_dms(pending_by_reviewer)
    _send_channel_summary(pending_by_repo, slack_map)

    print("Morning summary complete.")


if __name__ == "__main__":
    main()
