#!/usr/bin/env python3
"""
Nightly System & SEO Health Reporter
Runs via Render Cron Job daily at 02:00 UTC.

1. Fetches system + SEO snapshot from the mission-control API.
2. Generates Markdown report and commits to GitHub repo via Contents API.
3. Sends short status message to Telegram.
"""
import os
import sys
import json
import base64
from datetime import datetime, timezone
import requests

def fetch_snapshot(api_url):
    """Fetch health and SEO snapshot from server."""
    if not api_url:
        print("WARN: REPORT_API_URL not configured. Using fallback local payload.")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "Warning",
            "memory": {"mem_used_pct": 0, "mem_avail_mb": 0, "swap_used_pct": 0, "status": "unreachable"},
            "seo": {"recent_count": 0, "recent_articles_48h": []}
        }
    try:
        # In case server uses self-signed cert on 8443
        resp = requests.get(api_url, timeout=25, verify=False, auth=(os.environ.get("REPORT_API_USER", ""), os.environ.get("REPORT_API_PASS", "")))
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"ERROR fetching snapshot from {api_url}: {exc}")
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "Pressure",
            "error": str(exc),
            "memory": {"status": "unreachable"},
            "seo": {"recent_count": 0, "recent_articles_48h": []}
        }

def build_markdown_report(snap):
    """Create publication-grade Markdown report."""
    ts = snap.get("timestamp", datetime.now(timezone.utc).isoformat())
    status = snap.get("overall_status", "Unknown")
    mem = snap.get("memory", {})
    seo = snap.get("seo", {})
    recent_articles = seo.get("recent_articles_48h", [])
    
    status_emoji = "🟢" if status == "OK" else ("🟡" if status == "Warning" else "🔴")

    lines = [
        f"# Nightly Agent OS & SEO Health Report",
        f"",
        f"- **Date & Time:** `{ts}`",
        f"- **Overall Status:** {status_emoji} **{status.upper()}**",
        f"- **Source Host:** `ubuntu-4gb-nbg1-1`",
        f"",
        f"---",
        f"",
        f"## 1. System & Memory Health",
        f"",
        f"| Metric | Value | Threshold / Target | Status |",
        f"| :--- | :--- | :--- | :--- |",
        f"| **RAM Used** | `{mem.get('mem_used_pct', 'N/A')}%` | `< 85%` | `{'OK' if mem.get('mem_used_pct', 0) < 85 else 'WARN'}` |",
        f"| **RAM Available** | `{mem.get('mem_avail_mb', 'N/A')} MB` | `> 500 MB` | `{'OK' if mem.get('mem_avail_mb', 0) > 500 else 'WARN'}` |",
        f"| **Swap Utilization** | `{mem.get('swap_used_pct', 'N/A')}%` | `< 85%` | `{'OK' if mem.get('swap_used_pct', 0) < 85 else 'WARN'}` |",
        f"",
    ]

    top = mem.get("top_consumers", [])
    if top:
        lines.extend([
            f"### Top Memory Consumers",
            f"",
            f"| PID | RSS (MB) | Process Command |",
            f"| :--- | :--- | :--- |",
        ])
        for p in top[:5]:
            lines.append(f"| `{p.get('pid')}` | `{p.get('rss_mb')} MB` | `{p.get('cmd')}` |")
        lines.append("")

    lines.extend([
        f"---",
        f"",
        f"## 2. SEO Content Pipeline (Last 24–48 Hours)",
        f"",
        f"- **Recent Articles Generated / Published:** `{len(recent_articles)}`",
        f"",
    ])

    if recent_articles:
        lines.extend([
            f"| Job ID | Target Keyword | Priority | Status | Created Date |",
            f"| :--- | :--- | :--- | :--- | :--- |",
        ])
        for a in recent_articles:
            lines.append(f"| `{a.get('job_id')}` | **{a.get('keyword')}** | `{a.get('priority')}` | `{a.get('status')}` | `{a.get('created', '')[:19]}` |")
        lines.append("")
    else:
        lines.append("_No new articles processed in the last 48 hours._\n")

    lines.extend([
        f"---",
        f"",
        f"## 3. Operational Safeguards",
        f"- **Kanban limit:** `max_in_progress = 3` (1 per profile)",
        f"- **Model routing:** OpenRouter for critical / verification; OmniRoute for bulk / background.",
        f"- **Health Monitor:** Cron active every 5 min.",
        f"",
        f"---",
        f"*Generated automatically by Render Nightly Cron Reporter.*"
    ])

    return "\n".join(lines)

def build_telegram_summary(snap):
    """Build short Telegram summary string."""
    status = snap.get("overall_status", "Unknown")
    status_emoji = "🟢" if status == "OK" else ("🟡" if status == "Warning" else "🔴")
    mem = snap.get("memory", {})
    seo = snap.get("seo", {})
    recent = seo.get("recent_articles_48h", [])
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    msg = [
        f"{status_emoji} <b>Nightly Agent OS Report ({date_str})</b>",
        f"",
        f"• <b>Status:</b> {status.upper()}",
        f"• <b>RAM:</b> {mem.get('mem_used_pct', 'N/A')}% used ({mem.get('mem_avail_mb', 'N/A')}MB free)",
        f"• <b>Swap:</b> {mem.get('swap_used_pct', 'N/A')}% used",
        f"• <b>SEO Articles (48h):</b> {len(recent)} processed",
    ]

    if recent:
        msg.append("")
        msg.append("<b>Latest SEO:</b>")
        for a in recent[:3]:
            msg.append(f"• {a.get('keyword')} (<i>{a.get('status')}</i>)")

    msg.append("")
    msg.append("📁 <i>Full report committed to GitHub.</i>")
    return "\n".join(msg)

def send_telegram(bot_token, chat_id, text, topic_id=None):
    """Send summary message via Telegram Bot API with optional forum topic."""
    if not bot_token or not chat_id:
        print("WARN: Telegram token or chat ID not set. Skipping Telegram notification.")
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        if topic_id:
            payload["message_thread_id"] = int(topic_id)
        res = requests.post(url, json=payload, timeout=15)
        res.raise_for_status()
        print("SUCCESS: Telegram message delivered.")
        return True
    except Exception as e:
        print(f"ERROR sending Telegram message: {e}")
        return False

def commit_github_report(token, repo, branch, path_dir, content_md):
    """Commit report to GitHub via REST API."""
    if not token or not repo:
        print("WARN: GitHub token or repo not configured. Skipping GitHub commit.")
        return False
    
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{date_str}-nightly.md"
    file_path = f"{path_dir.rstrip('/')}/{filename}"
    api_url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # Check if file exists to get SHA for update
    sha = None
    try:
        get_res = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=15)
        if get_res.status_code == 200:
            sha = get_res.json().get("sha")
    except Exception:
        pass
    
    encoded_content = base64.b64encode(content_md.encode("utf-8")).decode("utf-8")
    commit_payload = {
        "message": f"Nightly health & SEO report for {date_str}",
        "content": encoded_content,
        "branch": branch
    }
    if sha:
        commit_payload["sha"] = sha
        
    try:
        put_res = requests.put(api_url, headers=headers, json=commit_payload, timeout=20)
        put_res.raise_for_status()
        print(f"SUCCESS: Report committed to https://github.com/{repo}/blob/{branch}/{file_path}")
        return True
    except Exception as e:
        print(f"ERROR committing to GitHub: {e}")
        return False

def main():
    print(f"--- Nightly Report Runner Started at {datetime.now(timezone.utc).isoformat()} ---")
    
    api_url = os.environ.get("REPORT_API_URL", "http://127.0.0.1:8899/api/v1/report/snapshot")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    gh_token = os.environ.get("GITHUB_TOKEN")
    gh_repo = os.environ.get("GITHUB_REPO", "BRIGHTMASTERS/nightly-reports")
    gh_branch = os.environ.get("GITHUB_BRANCH", "main")
    gh_path = os.environ.get("GITHUB_REPORTS_PATH", "reports")
    
    # Disable urllib3 insecure warnings for self-signed cert checks
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    snapshot = fetch_snapshot(api_url)
    markdown_content = build_markdown_report(snapshot)
    telegram_text = build_telegram_summary(snapshot)
    
    print("\n--- Telegram Summary Preview ---")
    print(telegram_text)
    
    # 1. Commit to GitHub
    commit_github_report(gh_token, gh_repo, gh_branch, gh_path, markdown_content)
    
    # 2. Send Telegram
    topic_id = os.environ.get("TELEGRAM_TOPIC_ID")
    send_telegram(bot_token, chat_id, telegram_text, topic_id)
    
    print(f"--- Nightly Report Runner Finished ---")

if __name__ == "__main__":
    main()
