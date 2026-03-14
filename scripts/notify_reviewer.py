# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Notify a single reviewer via Slack DM (called by reusable workflow)."""

from __future__ import annotations

import os
import sys

from scripts import github_client, slack_client, user_mapper, format_slack


def main() -> None:
    pr_url = os.environ["PR_URL"]
    pr_title = os.environ["PR_TITLE"]
    pr_number = os.environ["PR_NUMBER"]
    repo_name = os.environ["REPO_NAME"]
    reviewer_login = os.environ["REVIEWER_LOGIN"]
    requested_by = os.environ["REQUESTED_BY_LOGIN"]

    # Skip draft PRs — no notification needed until ready for review.
    owner, repo = repo_name.split("/", 1)
    pr_data = github_client.get_pr(owner, repo, int(pr_number))
    if pr_data.get("draft"):
        print(f"PR {repo_name}#{pr_number} is a draft, skipping notification.")
        return

    slack_id = user_mapper.resolve(reviewer_login)
    if slack_id is None:
        print(
            f"Could not resolve Slack user for {reviewer_login}, skipping DM.",
            file=sys.stderr,
        )
        return

    blocks = format_slack.rerequest_dm_blocks(
        repo_name=repo_name,
        pr_number=pr_number,
        pr_title=pr_title,
        pr_url=pr_url,
        requested_by=requested_by,
    )
    slack_client.send_dm(slack_id, blocks, text=f"Review requested on {repo_name}#{pr_number}")
    print(f"Sent DM to {reviewer_login} ({slack_id}) for {repo_name}#{pr_number}")


if __name__ == "__main__":
    main()
