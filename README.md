# PR Review Bot

Slack notification bot for pending PR reviews in the fractalyze org.

## Features

- **Morning Summary** (weekdays 9 AM KST): scans whitelisted repos, sends
  individual DMs to reviewers and a summary to #pr-reviews channel
- **On-demand Summary** (`/show-pr`): type `/show-pr` in #pr-reviews to
  trigger the same summary instantly
- **Real-time Notification**: when a reviewer is assigned to a PR, sends a
  Slack DM immediately

## Architecture

```
fractalyze/pr-review-bot (this repo)
├── Morning Summary: cron → scan whitelisted repos → Slack DMs + channel table
├── Slack App: /show-pr command → on-demand summary → channel table
└── Re-request Notify: per-repo caller workflow → reusable workflow → Slack DM

Each member repo:
└── .github/workflows/pr-review-notify.yml (caller, ~20 lines)
    └── pull_request: [review_requested] → real-time DM
```

## Setup

### 1. Slack App

1. Create a new Slack App at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable **Socket Mode** (Settings → Socket Mode → toggle on)
   - Generate an App-Level Token with `connections:write` scope → copy `xapp-...`
3. Add Bot Token Scopes (OAuth & Permissions):
   `chat:write`, `users:read`, `users:read.email`, `commands`
4. Create Slash Command (Slash Commands → Create New Command):
   - Command: `/show-pr`
   - Description: `Show pending PR reviews`
5. Install to workspace and copy the Bot Token (`xoxb-...`)
6. Invite bot to the summary channel: `/invite @pr-review-bot`

### 2. GitHub Secrets (org-level)

| Secret | Description |
|--------|-------------|
| `GH_PAT` | Fine-grained PAT with `repo`, `read:org`, `read:user` scopes |
| `PR_REVIEW_SLACK_BOT_TOKEN` | Slack Bot OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Slack App-Level Token for Socket Mode (`xapp-...`) |
| `SLACK_SUMMARY_CHANNEL_ID` | Channel ID for daily summary (e.g., `C01234ABC`) |

### 3. Configure Monitored Repos

Set a **repository variable** in GitHub Settings → Secrets and variables →
Actions → Variables:

| Variable | Description |
|----------|-------------|
| `MONITORED_REPOS` | Comma-separated repo names (e.g., `zkx,riscv-witness`) |

For local development, copy `config.yml.example` to `config.yml` and fill in
the repo names. The scripts read `MONITORED_REPOS` env var first, then fall
back to `config.yml`.

### 4. Deploy Caller Workflows

```bash
# Preview
GH_PAT=ghp_... python setup/deploy_caller_workflow.py --dry-run

# Deploy
GH_PAT=ghp_... python setup/deploy_caller_workflow.py
```

## Usage

### Morning Summary

Runs automatically on weekdays at 9 AM KST. Trigger manually:

```bash
gh workflow run morning-summary.yml
```

### On-demand Summary (Slack)

Type `/show-pr` in `#pr-reviews` to get the current PR summary instantly.

### Running the Slack App

The Slack app runs as a long-lived process using Socket Mode (no public URL
needed):

```bash
export GH_PAT=ghp_...
export PR_REVIEW_SLACK_BOT_TOKEN=xoxb-...
export SLACK_APP_TOKEN=xapp-...
export SLACK_SUMMARY_CHANNEL_ID=C01234ABC
export MONITORED_REPOS=zkx,riscv-witness

python -m scripts.slack_app
```

## Verification

1. `workflow_dispatch` → morning-summary → check DMs and channel
2. Create test PR → add reviewer → verify DM arrives (~1 min)
3. Re-request review (↻ button) → verify DM arrives
4. Check Actions step summary for unmapped users
