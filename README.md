# PR Review Bot

Slack notification bot for pending PR reviews in the fractalyze org.

## Features

- **Morning Summary** (weekdays 9 AM KST): scans whitelisted repos, sends
  individual DMs to reviewers and a summary to #pr-reviews channel
- **Real-time Notification**: when a reviewer is assigned to a PR, sends a
  Slack DM immediately
- **Comment Re-request**: post `/re-request @alice @bob` on a PR to
  re-request reviews via GitHub API and notify via Slack DM

## Architecture

```
fractalyze/pr-review-bot (this repo)
├── Morning Summary: cron → scan whitelisted repos → Slack DMs + channel table
├── Re-request Notify: per-repo caller workflow → reusable workflow → Slack DM
└── Comment Re-request: /re-request comment → API review request + Slack DM

Each member repo:
└── .github/workflows/pr-review-notify.yml (caller, ~30 lines)
    ├── pull_request: [review_requested] → real-time DM
    └── issue_comment: [created] → /re-request handling
```

## Setup

### 1. Slack App

1. Create a new Slack App at [api.slack.com/apps](https://api.slack.com/apps)
2. Add Bot Token Scopes: `chat:write`, `users:read`, `users:read.email`
3. Install to workspace and copy the Bot Token (`xoxb-...`)
4. Invite bot to the summary channel: `/invite @pr-review-bot`

### 2. GitHub Secrets (org-level)

| Secret | Description |
|--------|-------------|
| `GH_PAT` | Fine-grained PAT with `repo`, `read:org`, `read:user` scopes |
| `PR_REVIEW_SLACK_BOT_TOKEN` | Slack Bot OAuth Token (`xoxb-...`) |
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

### Re-request Review

Comment on a PR:

```
/re-request @alice
/re-request @alice @bob
```

The bot will:
1. Call GitHub API to formally request review
2. Send Slack DMs to each reviewer
3. Add a 👀 reaction to confirm processing

## Verification

1. `workflow_dispatch` → morning-summary → check DMs and channel
2. Create test PR → add reviewer → verify DM arrives (~1 min)
3. Re-request review (↻ button) → verify DM arrives
4. Comment `/re-request @user` → verify review request + DM + 👀 reaction
5. Check Actions step summary for unmapped users
