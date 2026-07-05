---
name: daily-rss-scan
description: >-
  Scrapes configured CFP and tech blog URLs, detects new links against
  track_files history, emails a daily digest, and commits updates. Use when
  running the daily MyRSS scan, checking for new CFPs or conceptual tech
  posts, or when the user mentions daily RSS, feed monitoring, or MyRSS.
---

# Daily RSS Scan

Run once per day. Scrape sources, diff against history, email only real updates, then persist and push.

## Sources

| Type | File | What to report |
|------|------|----------------|
| CFP | `urls/cfp_urls.json` | Any new call-for-papers |
| Tech | `urls/tech_urls.json` | Conceptual / educational posts only — skip routine news, releases, and announcements |

Each entry: `{ "id": { "name": "...", "url": "..." } }`.

## Track files

- Directory: `track_files/`
- One file per source: `track_files/{type}-{id}.md` (e.g. `cfp-23.md`, `tech-1.md`)
- Each entry in the file: **title**, **link**, **concise description** (one line; helps dedupe later)

## Workflow

Copy and track progress:

```
Daily scan:
- [ ] 1. Load url lists
- [ ] 2. Scrape and diff each source
- [ ] 3. Send digest email (if updates exist)
- [ ] 4. Update track_files
- [ ] 5. Commit and push
```

### Step 1 — Load sources

Read `urls/cfp_urls.json` and `urls/tech_urls.json`.

### Step 2 — Scrape and diff

For **every** URL in both files:

**No track file yet** (`track_files/{type}-{id}.md` missing):

1. Scrape the URL.
2. Save all current links to a new track file using the template below.
3. Do **not** include this source in today's email — baseline only.

**Track file exists**:

1. Scrape the URL again.
2. Compare links to the track file (match primarily on URL; use title/description to catch near-duplicates).
3. Collect only **new** items for the email.
4. Append new items to the track file after the email step.

**Filtering**

- **CFP** (`cfp_urls`): report every new CFP link.
- **Tech** (`tech_urls`): report only posts that teach a concept, pattern, architecture, or deep technical idea. Skip product launches, hiring, event recaps, and shallow news.

**Scraping tools** (in order):

1. Web Scraper MCP — read tool schema before calling.
2. If unavailable: browser MCP (`cursor-ide-browser`) or `WebFetch`.

On scrape failure for one URL: log the error, continue with remaining URLs, mention failures in the email if any updates were sent.

### Step 3 — Email digest

Send only when at least one new item was found across all sources.

- **MCP**: Resend (`send-email`) — read tool schema before calling.
- **To**: `m.shokrnezhad@gmail.com`
- **From**: use the user's configured Resend sender address (ask once if unknown; do not invent).
- **Subject**: `MyRSS Daily — {YYYY-MM-DD}` or `MyRSS Daily — {YYYY-MM-DD} ({N} updates)`

**Body template**:

```markdown
# MyRSS Daily — {date}

## CFP updates
{For each new CFP:}
### {title}
{link}
{one-line description}

## Tech reads
{For each new conceptual post:}
### {title}
{link}
{one-line description}

---
{If any scrape failures: list source name + URL + error}
```

If no updates anywhere: skip email; still commit if track files were created during first-run baselines.

### Step 4 — Update track files

Write or append using this entry format:

```markdown
## {title}
- **Link**: {url}
- **Description**: {one concise line}
- **First seen**: {YYYY-MM-DD}
```

New baselines: file header `# {source name}` then all entries.

### Step 5 — Git

Only when track files changed:

```bash
git add track_files/
git commit -m "MyRSS daily scan — {YYYY-MM-DD}"
git push
```

Do not commit unrelated files. Do not push if commit fails.

## Example

**First run** for `cfp-23` (IEEE NetMag): scrape → write `track_files/cfp-23.md` with 8 CFPs → no email for that source.

**Next day**: scrape again → 1 new CFP → include in email → append to `track_files/cfp-23.md` → commit `MyRSS daily scan — 2026-07-05` → push.

## Rules

- Process all URLs in both JSON files every run.
- Never email baseline-only first scrapes.
- Keep descriptions short and distinct per link.
- Prefer link URL as the dedup key.
- Finish the full workflow in one run; do not stop after scraping.
