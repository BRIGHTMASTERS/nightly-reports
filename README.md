# Nightly Reports

Automated nightly health, memory, and SEO reports orchestrated via **Render Cron Jobs**.

## Architecture & Flow
1. **Schedule:** Runs every day at **02:00 UTC** via Render Cron (`schedule: '0 2 * * *'`).
2. **Data Collection:** Pulls a live system & SEO health snapshot from the Agent OS endpoint (`/api/v1/report/snapshot`).
3. **Telegram Alert:** Dispatches a concise status summary to Telegram via Bot API (Topic `1553` - "Health and SEO").
4. **GitHub Archival:** Commits the full detailed Markdown report to `/reports/YYYY-MM-DD-nightly.md`.

## Setup on Render
1. Create a **New Blueprint Instance** on [Render Dashboard](https://dashboard.render.com/blueprints).
2. Point it to this repository: `https://github.com/BRIGHTMASTERS/nightly-reports`.
3. Provide the required secrets in the Render Environment prompt:
   - `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather
   - `TELEGRAM_CHAT_ID`: Destination Telegram chat ID (pre-configured: `-1003878517539`)
   - `TELEGRAM_TOPIC_ID`: Destination Telegram topic/thread ID (pre-configured: `1553` for Health and SEO)
   - `GITHUB_TOKEN`: Personal Access Token with `repo` / `Contents: write` scope
