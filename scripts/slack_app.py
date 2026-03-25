# Copyright 2026 Fractalyze Inc. All rights reserved.

"""Slack Bolt app: listens for /show-pr command via Socket Mode."""

from __future__ import annotations

import logging
import os
import threading

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from scripts import morning_summary, format_slack, slack_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = App(token=os.environ["PR_REVIEW_SLACK_BOT_TOKEN"])


def _run_summary(channel_id: str, user_id: str) -> None:
    """Collect pending reviews and post summary to the channel."""
    try:
        pending_by_repo = morning_summary.collect_pending_reviews()

        if not pending_by_repo:
            slack_client.post_message(
                channel_id,
                blocks=[],
                text=":white_check_mark: No pending reviews found!",
            )
            return

        slack_map = morning_summary.build_slack_map(pending_by_repo)
        blocks = format_slack.channel_summary_blocks(pending_by_repo, slack_map)
        total = sum(len(prs) for prs in pending_by_repo.values())
        slack_client.post_message(
            channel_id,
            blocks,
            text=f"PR Review Summary: {total} PRs pending",
        )
        logger.info(
            "Posted on-demand summary: %d PRs across %d repos (requested by %s)",
            total,
            len(pending_by_repo),
            user_id,
        )
    except Exception:
        logger.exception("Failed to generate PR summary")
        slack_client.post_message(
            channel_id,
            blocks=[],
            text=":x: Failed to generate PR summary. Check bot logs.",
        )


@app.command("/show-pr")
def handle_show_pr(ack, command):
    """Handle the /show-pr slash command."""
    ack(":hourglass_flowing_sand: Scanning repos for pending reviews...")

    channel_id = command["channel_id"]
    user_id = command["user_id"]

    thread = threading.Thread(
        target=_run_summary, args=(channel_id, user_id), daemon=True
    )
    thread.start()


def main() -> None:
    app_token = os.environ.get("SLACK_APP_TOKEN", "")
    if not app_token:
        raise RuntimeError(
            "SLACK_APP_TOKEN (xapp-...) is required for Socket Mode"
        )
    handler = SocketModeHandler(app, app_token)
    logger.info("Starting Slack app in Socket Mode...")
    handler.start()


if __name__ == "__main__":
    main()
