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
- [ ] 0. Sync main (no new branches)
- [ ] 1. Retry pending outbox emails (`*.off.md`)
- [ ] 2. Load url lists
- [ ] 3. Scrape and diff each source
- [ ] 4. Save digest to outbox and send (if updates exist)
- [ ] 5. Update track_files
- [ ] 6. Commit and push to main
```

### Step 0 — Sync main

Work **directly on `main`**. This workflow must be fully automated with no PRs or branch merges.

```bash
git checkout main
git pull origin main
```

**Do not:**

- Create a new branch
- Open a pull request
- Push to any branch other than `main`

### Step 1 — Retry pending outbox emails

Before scraping, check `email_outbox/` for unsent digests (`{YYYY-MM-DD}.off.md`). Attempt to send each one via the Resend REST API (`RESEND_API_KEY`). On success, rename to `{YYYY-MM-DD}.sent.md`.

This ensures digests survive API outages and are delivered on the next run.

### Step 2 — Load sources

Read `urls/cfp_urls.json` and `urls/tech_urls.json`.

### Step 3 — Scrape and diff

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

### Step 4 — Email digest

Send only when at least one new item was found across all sources.

- **API**: Resend REST API via `scripts/daily_scan.py` using `RESEND_API_KEY` (not MCP).
- **To**: `m.shokrnezhad@gmail.com`
- **From**: `RESEND_FROM` env var, default `onboarding@resend.dev`
- **Subject**: `MyRSS Daily — {YYYY-MM-DD}` or `MyRSS Daily — {YYYY-MM-DD} ({N} updates)`

**Outbox** (`email_outbox/`):

- Save every digest body before sending: `{YYYY-MM-DD}.off.md`
- File format: YAML frontmatter with `subject:` line, then markdown body
- On successful send, rename to `{YYYY-MM-DD}.sent.md`
- If send fails, leave as `.off.md` — next run retries before scraping

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

If no updates anywhere: skip email; still commit if track files or outbox files changed during first-run baselines.

### Step 5 — Update track files

Write or append using this entry format:

```markdown
## {title}
- **Link**: {url}
- **Description**: {one concise line}
- **First seen**: {YYYY-MM-DD}
```

New baselines: file header `# {source name}` then all entries.

### Step 6 — Git

Stay on `main`. When track files or outbox files changed:

```bash
git checkout main
git add track_files/ email_outbox/
git commit -m "MyRSS daily scan — {YYYY-MM-DD}"
git push origin main
```

Do not commit unrelated files. Do not push if commit fails. Do not create branches or PRs.

## Example

**First run** for `cfp-23` (IEEE NetMag): scrape → write `track_files/cfp-23.md` with 8 CFPs → no email for that source.

**Next day**: pull `main` → scrape again → 1 new CFP → include in email → append to `track_files/cfp-23.md` → commit on `main` → `git push origin main`.

## Rules

- Work on `main` only — no feature branches, no pull requests.
- Process all URLs in both JSON files every run.
- Never email baseline-only first scrapes.
- Keep descriptions short and distinct per link.
- Prefer link URL as the dedup key.
- Finish the full workflow in one run; do not stop after scraping.
