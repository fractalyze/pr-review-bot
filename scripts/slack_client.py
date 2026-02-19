# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Slack Web API client wrapper using slack-sdk."""

from __future__ import annotations

import os

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

_client: WebClient | None = None


def _get_client() -> WebClient:
    global _client
    if _client is None:
        token = os.environ.get("SLACK_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("SLACK_BOT_TOKEN environment variable is not set")
        _client = WebClient(token=token)
    return _client


def lookup_user_by_email(email: str) -> str | None:
    """Look up a Slack user ID by email address.

    Returns the user ID if found, None otherwise.
    """
    try:
        resp = _get_client().users_lookupByEmail(email=email)
        return resp["user"]["id"]
    except SlackApiError as e:
        if e.response["error"] == "users_not_found":
            return None
        raise


def list_users() -> list[dict]:
    """List all users in the workspace (for fallback name matching)."""
    users: list[dict] = []
    cursor = None
    while True:
        resp = _get_client().users_list(cursor=cursor, limit=200)
        users.extend(resp["members"])
        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return users


def open_dm(user_id: str) -> str:
    """Open a DM channel with a user. Returns the channel ID."""
    resp = _get_client().conversations_open(users=[user_id])
    return resp["channel"]["id"]


def post_message(channel_id: str, blocks: list[dict], text: str = "") -> None:
    """Post a Block Kit message to a channel or DM."""
    _get_client().chat_postMessage(
        channel=channel_id,
        blocks=blocks,
        text=text or "PR Review Notification",
    )


def send_dm(user_id: str, blocks: list[dict], text: str = "") -> None:
    """Open a DM and post a message in one call."""
    channel_id = open_dm(user_id)
    post_message(channel_id, blocks, text)
