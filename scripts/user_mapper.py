# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Map GitHub logins to Slack user IDs."""

from __future__ import annotations

import sys

from scripts import github_client, slack_client

_cache: dict[str, str | None] = {}
_slack_users: list[dict] | None = None


def _get_slack_users() -> list[dict]:
    """Lazily fetch and cache the full Slack user list."""
    global _slack_users
    if _slack_users is None:
        _slack_users = slack_client.list_users()
    return _slack_users


def _fuzzy_match_by_name(github_login: str, github_name: str) -> str | None:
    """Try to match a GitHub user to a Slack user by display name.

    Compares against Slack profile display_name and real_name
    (case-insensitive).
    """
    targets = {github_login.lower(), github_name.lower()} - {""}
    for user in _get_slack_users():
        if user.get("is_bot") or user.get("deleted"):
            continue
        profile = user.get("profile", {})
        display = profile.get("display_name", "").lower()
        real = profile.get("real_name", "").lower()
        if display in targets or real in targets:
            return user["id"]
    return None


def resolve(github_login: str) -> str | None:
    """Resolve a GitHub login to a Slack user ID.

    Strategy:
    1. Check in-memory cache
    2. Look up GitHub user's public email → Slack lookupByEmail
    3. Fuzzy match by display name as fallback
    4. Log failure to stderr and return None
    """
    if github_login in _cache:
        return _cache[github_login]

    slack_id = None

    # Step 1: try email-based lookup
    try:
        user_info = github_client.get_user_info(github_login)
        email = user_info.get("email")
        name = user_info.get("name", "")

        if email:
            slack_id = slack_client.lookup_user_by_email(email)

        # Step 2: fallback to name matching
        if slack_id is None:
            slack_id = _fuzzy_match_by_name(github_login, name)

    except Exception as e:
        print(f"WARNING: failed to resolve {github_login}: {e}", file=sys.stderr)

    if slack_id is None:
        print(
            f"WARNING: could not map GitHub user '{github_login}' to Slack",
            file=sys.stderr,
        )

    _cache[github_login] = slack_id
    return slack_id
