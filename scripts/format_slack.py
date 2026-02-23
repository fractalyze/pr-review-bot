# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Slack Block Kit message builders."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta


KST = timezone(timedelta(hours=9))


def _header(text: str) -> dict:
    return {"type": "header", "text": {"type": "plain_text", "text": text}}


def _section(markdown: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": markdown}}


def _divider() -> dict:
    return {"type": "divider"}


def _context(text: str) -> dict:
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text}],
    }


def _button(text: str, url: str) -> dict:
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": " "},
        "accessory": {
            "type": "button",
            "text": {"type": "plain_text", "text": text},
            "url": url,
            "action_id": "open_pr",
        },
    }


def _format_reviewer(login: str, slack_id: str | None) -> str:
    if slack_id:
        return f"<@{slack_id}>"
    return f"@{login}"


def _days_ago(opened_at: str) -> str:
    opened = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - opened
    days = delta.days
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


# ---------------------------------------------------------------------------
# Channel summary (morning, posted to #pr-reviews)
# ---------------------------------------------------------------------------

def channel_summary_blocks(
    pending_by_repo: dict[str, list[dict]],
    slack_map: dict[str, str | None],
) -> list[dict]:
    """Build blocks for the channel summary message.

    Args:
        pending_by_repo: {repo_full_name: [{pr_number, title, reviewers, ...}]}
        slack_map: {github_login: slack_user_id | None}
    """
    today = datetime.now(KST).strftime("%A, %B %-d")
    blocks: list[dict] = [_header(f"PR Review Summary \u2014 {today}")]

    total_prs = 0
    total_repos = 0

    for repo, prs in sorted(pending_by_repo.items()):
        if not prs:
            continue
        total_repos += 1
        total_prs += len(prs)

        lines = [f"*{repo}* \u2014 {len(prs)} pending review{'s' if len(prs) > 1 else ''}"]
        for pr in prs:
            reviewers = ", ".join(
                _format_reviewer(r, slack_map.get(r)) for r in pr["reviewers"]
            )
            lines.append(
                f"\u2022 <{pr['url']}|#{pr['number']} {pr['title']}>"
                f" \u2014 waiting on {reviewers}"
            )
        blocks.append(_section("\n".join(lines)))
        blocks.append(_divider())

    if blocks and blocks[-1]["type"] == "divider":
        blocks.pop()

    repo_word = "repo" if total_repos == 1 else "repos"
    blocks.append(
        _context(
            f"Total: {total_prs} PR{'s' if total_prs != 1 else ''} pending review"
            f" across {total_repos} {repo_word}"
        )
    )
    return blocks


# ---------------------------------------------------------------------------
# Individual DM (morning, one per reviewer)
# ---------------------------------------------------------------------------

def individual_dm_blocks(
    reviewer_login: str,
    prs_by_repo: dict[str, list[dict]],
) -> list[dict]:
    """Build blocks for a reviewer's morning DM.

    Args:
        reviewer_login: GitHub login of the reviewer
        prs_by_repo: {repo_full_name: [{number, title, url, author, created_at}]}
    """
    total = sum(len(prs) for prs in prs_by_repo.values())
    blocks: list[dict] = [
        _header(f"Good morning! You have {total} PR{'s' if total != 1 else ''} awaiting review"),
    ]

    for repo, prs in sorted(prs_by_repo.items()):
        for pr in prs:
            age = _days_ago(pr["created_at"])
            blocks.append(
                _section(
                    f"*{repo}*\n"
                    f"<{pr['url']}|#{pr['number']} {pr['title']}>\n"
                    f"Opened by @{pr['author']} \u00b7 {age}"
                )
            )
            blocks.append(_divider())

    if blocks and blocks[-1]["type"] == "divider":
        blocks.pop()

    return blocks


# ---------------------------------------------------------------------------
# Re-request DM (real-time, triggered by review_requested)
# ---------------------------------------------------------------------------

def rerequest_dm_blocks(
    repo_name: str,
    pr_number: str | int,
    pr_title: str,
    pr_url: str,
    requested_by: str,
) -> list[dict]:
    """Build blocks for a real-time re-request DM."""
    return [
        _section(
            f"*Review requested* on {repo_name} "
            f"<{pr_url}|#{pr_number}>\n"
            f"*@{requested_by}* requested your review on: {pr_title}"
        ),
        _button("Open PR", pr_url),
    ]
