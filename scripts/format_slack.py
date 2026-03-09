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


def _working_days_since(opened_at: str) -> int:
    """Count working days (Mon-Fri) between opened_at and now, excluding weekends."""
    opened = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    count = 0
    day = opened.date() + timedelta(days=1)
    today = now.date()
    while day <= today:
        if day.weekday() < 5:  # Mon=0 .. Fri=4
            count += 1
        day += timedelta(days=1)
    return count


def _days_ago(opened_at: str) -> str:
    days = _working_days_since(opened_at)
    if days == 0:
        return "today"
    if days == 1:
        return "1 working day ago"
    return f"{days} working days ago"


def _age_indicator(created_at: str) -> str:
    """Return a colored square emoji based on PR age in working days.

    0-1 working days: green (fresh)
    2 working days:   yellow (attention)
    3 working days:   orange (warning)
    4+ working days:  red (urgent)
    """
    days = _working_days_since(created_at)
    if days <= 1:
        return ":large_green_square:"
    if days == 2:
        return ":large_yellow_square:"
    if days == 3:
        return ":large_orange_square:"
    return ":large_red_square:"


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
    reviewer_counts: dict[str, int] = {}

    for repo, prs in sorted(pending_by_repo.items()):
        if not prs:
            continue
        total_repos += 1
        total_prs += len(prs)

        lines = [f"*{repo}* \u2014 {len(prs)} pending review{'s' if len(prs) > 1 else ''}"]
        for pr in prs:
            indicator = _age_indicator(pr["created_at"])
            age = _days_ago(pr["created_at"])
            author = _format_reviewer(pr["author"], slack_map.get(pr["author"]))
            reviewers = ", ".join(
                _format_reviewer(r, slack_map.get(r)) for r in pr["reviewers"]
            )
            lines.append(
                f"{indicator} <{pr['url']}|#{pr['number']} {pr['title']}>"
            )
            lines.append(
                f"    by {author} \u00b7 opened {age} \u00b7 waiting on {reviewers}"
            )

            for r in pr["reviewers"]:
                reviewer_counts[r] = reviewer_counts.get(r, 0) + 1

        blocks.append(_section("\n".join(lines)))
        blocks.append(_divider())

    if blocks and blocks[-1]["type"] == "divider":
        blocks.pop()

    # Reviewer leaderboard (separated from repo sections)
    if reviewer_counts:
        blocks.append(_divider())
        sorted_reviewers = sorted(
            reviewer_counts.items(), key=lambda x: x[1], reverse=True
        )
        leaderboard_lines = [":eyes: *Reviewer Leaderboard*"]
        for login, count in sorted_reviewers:
            name = _format_reviewer(login, slack_map.get(login))
            pr_word = "PR" if count == 1 else "PRs"
            leaderboard_lines.append(f"{name} \u2014 {count} {pr_word} pending")
        blocks.append(_section("\n".join(leaderboard_lines)))

    repo_word = "repo" if total_repos == 1 else "repos"
    blocks.append(
        _context(
            f"Total: {total_prs} PR{'s' if total_prs != 1 else ''} pending review"
            f" across {total_repos} {repo_word}"
        )
    )
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
