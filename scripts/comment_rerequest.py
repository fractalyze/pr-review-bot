# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Handle /re-request @user comments on PRs."""

from __future__ import annotations

import os
import re
import sys

from scripts import github_client, slack_client, user_mapper, format_slack

RE_REQUEST_PATTERN = re.compile(r"/re-request\s+((?:@[\w-]+\s*)+)")
MENTION_PATTERN = re.compile(r"@([\w-]+)")


def parse_reviewers(comment_body: str) -> list[str]:
    """Extract reviewer logins from a /re-request comment.

    Supports: /re-request @alice @bob
    """
    match = RE_REQUEST_PATTERN.match(comment_body.strip())
    if not match:
        return []
    return MENTION_PATTERN.findall(match.group(1))


def main() -> None:
    comment_body = os.environ["COMMENT_BODY"]
    pr_number = int(os.environ["PR_NUMBER"])
    repo_name = os.environ["REPO_NAME"]
    comment_id = int(os.environ["COMMENT_ID"])
    sender_login = os.environ["SENDER_LOGIN"]

    reviewers = parse_reviewers(comment_body)
    if not reviewers:
        print(f"No valid reviewers found in comment: {comment_body!r}")
        return

    owner, repo = repo_name.split("/")

    # Request reviews via GitHub API
    print(f"Requesting review from {reviewers} on {repo_name}#{pr_number}")
    try:
        github_client.request_reviewers(owner, repo, pr_number, reviewers)
    except Exception as e:
        print(f"ERROR: failed to request reviewers: {e}", file=sys.stderr)
        sys.exit(1)

    # Add eyes reaction to the comment
    try:
        github_client.add_comment_reaction(owner, repo, comment_id)
    except Exception as e:
        print(f"WARNING: failed to add reaction: {e}", file=sys.stderr)

    # Fetch PR details for the DM
    prs = github_client.list_open_prs(owner, repo)
    pr = next((p for p in prs if p["number"] == pr_number), None)
    pr_title = pr["title"] if pr else f"#{pr_number}"
    pr_url = pr["html_url"] if pr else f"https://github.com/{repo_name}/pull/{pr_number}"

    # Send Slack DMs to each reviewer
    for login in reviewers:
        slack_id = user_mapper.resolve(login)
        if slack_id is None:
            continue

        blocks = format_slack.rerequest_dm_blocks(
            repo_name=repo_name,
            pr_number=pr_number,
            pr_title=pr_title,
            pr_url=pr_url,
            requested_by=sender_login,
        )
        try:
            slack_client.send_dm(
                slack_id, blocks, text=f"Review re-requested on {repo_name}#{pr_number}"
            )
            print(f"Sent DM to {login} ({slack_id})")
        except Exception as e:
            print(f"WARNING: failed to send DM to {login}: {e}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    main()
