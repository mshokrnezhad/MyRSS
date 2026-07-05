# MyRSS

Keeping up with conference calls for papers (CFPs) and high-quality engineering blogs takes time, and RSS feeds are not always available or reliable. It is easy to miss a new CFP deadline or a deep technical post buried in everyday product news.

MyRSS is a lightweight monitoring setup for curated sources. A daily agent scrapes configured URLs, compares results against local history, emails only what is new, and commits updated track files to this repository.

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Daily Scan](#daily-scan)
- [Thank You](#thank-you-)

## Overview

MyRSS tracks two kinds of sources:

| Type | Config file | What gets reported |
|------|-------------|-------------------|
| **CFP** | `urls/cfp_urls.json` | New calls for papers |
| **Tech** | `urls/tech_urls.json` | Conceptual or educational engineering posts — not routine news, releases, or announcements |

Each run follows a simple diff workflow:

1. Scrape every configured URL.
2. Compare links against history in `track_files/`.
3. On the **first scrape** for a source, save a baseline and do **not** send an alert.
4. On later runs, email new items only, update track files, then commit and push.

Digest emails are sent to `m.shokrnezhad@gmail.com` when there are updates.

## Repository Structure

```
MyRSS/
├── urls/
│   ├── cfp_urls.json      # CFP sources (id, name, url)
│   └── tech_urls.json     # Tech blog sources (id, name, url)
├── track_files/           # Per-source link history (one .md file per source)
└── .cursor/skills/
    └── daily-rss-scan/    # Agent skill for the daily workflow
        └── SKILL.md
```

**URL config format** — each file maps an id to a source:

```json
{
  "23": {
    "name": "IEEE NetMag",
    "url": "https://www.comsoc.org/publications/magazines/ieee-network/cfp"
  }
}
```

**Track files** — stored as `track_files/{type}-{id}.md` (e.g. `cfp-23.md`, `tech-1.md`). Each entry records a title, link, concise description, and first-seen date.

## Daily Scan

The daily workflow is defined in [`.cursor/skills/daily-rss-scan/SKILL.md`](.cursor/skills/daily-rss-scan/SKILL.md).

**Run manually in Cursor:**

```
@daily-rss-scan
```

Or ask the agent to run the daily MyRSS scan.

**Run on a schedule** (example with the loop skill):

```
/loop 1d @daily-rss-scan
```

**Tools used by the agent:**

| Step | Tool |
|------|------|
| Scraping | Web Scraper MCP (fallback: browser MCP or WebFetch) |
| Email | Resend MCP (`send-email`) |
| History | Git commit + push to `track_files/` |

Commit message format: `MyRSS daily scan — YYYY-MM-DD`.

---

## Thank You <img src="https://raw.githubusercontent.com/Tarikul-Islam-Anik/Animated-Fluent-Emojis/master/Emojis/Hand%20gestures/Folded%20Hands.png" alt="Folded Hands" width="20" height="20" />

Thank you for checking out MyRSS. We hope it helps you stay on top of CFPs and worthwhile tech reads without drowning in noise.

**How you can contribute:**

- Add CFP or tech blog sources to `urls/cfp_urls.json` or `urls/tech_urls.json`
- Improve scrape reliability or filtering in the daily scan skill
- Report sources that break or produce noisy results
- Suggest better deduplication or email digest formatting
- Open issues or pull requests with fixes and ideas

We look forward to your ideas and contributions!
