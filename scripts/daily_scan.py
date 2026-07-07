#!/usr/bin/env python3
"""MyRSS daily scan: scrape sources, diff against track_files, optionally email."""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
URLS_DIR = ROOT / "urls"
TRACK_DIR = ROOT / "track_files"
OUTBOX_DIR = ROOT / "email_outbox"
TODAY = date.today().isoformat()

DIGEST_TO = os.getenv("RESEND_TO", "m.shokrnezhad@gmail.com")
RESEND_FROM = os.getenv("RESEND_FROM", "onboarding@resend.dev")
RESEND_API_URL = "https://api.resend.com/emails"

TECH_SKIP_PATTERNS = (
    r"\bgeforce now\b",
    r"\bgames (coming|list)\b",
    r"\b(now available|introducing|announc\w+|launch\w+|unveil\w+)\b",
    r"\b(hiring|we're hiring|join our team)\b",
    r"\b(gdc|event recap|conference recap)\b",
    r"\b(partnership|collaborat\w+ with|bring .+ to .+ community)\b",
    r"\b(plans to upskill|graduation season|celebrating)\b",
    r"\bstrategic priorities\b",
    r"\bcapital partners\b",
    r"\bstream processing brings\b",
    r"\b(the new .+ cache api|smart placement cache)\b",
    r"\btalent from\b",
)
TECH_INCLUDE_PATTERNS = (
    r"\bhow (we|to|open)\b",
    r"\b(from .+ to .+|architecture|pattern|migration|moderniz)\b",
    r"\b(scaling|performance|deep dive|under the hood)\b",
    r"\b(research|algorithm|distributed|infrastructure)\b",
    r"\bbuilding (a|on|with)\b",
    r"\blessons from\b",
    r"\bdesign\b",
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MyRSS/1.0; +https://github.com/mshokrnezhad/MyRSS)"
    )
}


@dataclass
class Item:
    title: str
    link: str
    description: str


def fetch(url: str) -> str:
    headers = {
        **HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    return resp.text


def parse_ieee_cfp(html: str, base_url: str) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/cfp/" not in href or href.rstrip("/").endswith("/cfp"):
            continue
        if href.startswith("/"):
            link = urljoin("https://www.comsoc.org", href)
        elif href.startswith("http"):
            link = href
        else:
            link = urljoin(base_url, href)
        if link in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 10:
            continue
        seen.add(link)
        items.append(Item(title=title, link=link, description=f"IEEE CFP — {title[:80]}"))

    return items


def parse_airbnb_tech(html: str, base_url: str) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()

    for heading in soup.find_all(["h2", "h3", "h4"]):
        title = heading.get_text(" ", strip=True)
        if not title or len(title) < 15:
            continue
        link_tag = heading.find_next("a", href=True)
        if not link_tag:
            continue
        href = link_tag["href"]
        if "medium.com/airbnb-engineering" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        desc_tag = heading.find_next("p")
        desc = desc_tag.get_text(" ", strip=True)[:160] if desc_tag else title[:120]
        items.append(Item(title=title, link=href, description=desc))

    if items:
        return items[:30]

    for match in re.finditer(
        r"\[Visit Link\]\((https://medium\.com/airbnb-engineering/[^)]+)\)",
        html,
    ):
        link = match.group(1)
        if link in seen:
            continue
        seen.add(link)
        slug = link.rstrip("/").split("/")[-1]
        title = slug.replace("-", " ").title()
        items.append(Item(title=title, link=link, description=f"Airbnb engineering post — {title}"))
    return items[:30]


def parse_blog_posts_generic(
    html: str, base_url: str, path_filter: re.Pattern | None = None
) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        link = urljoin(base_url, href)
        parsed = urlparse(link)
        base_parsed = urlparse(base_url)
        if parsed.netloc and parsed.netloc != base_parsed.netloc:
            continue
        path = parsed.path
        if path_filter and not path_filter.search(path):
            continue
        if any(
            skip in path.lower()
            for skip in (
                "/author/",
                "/tag/",
                "/page/",
                "/category/",
                "/topics/",
                "/channel/",
                "/jobs",
                "/legal",
                "/privacy",
            )
        ):
            continue
        if link.rstrip("/") == base_url.rstrip("/"):
            continue
        if len(path.strip("/").split("/")) < 2:
            continue
        if link in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 12:
            continue
        if title.lower() in ("read more", "continue reading", "home", "subscribe"):
            continue
        seen.add(link)
        desc = ""
        parent = a.find_parent(["article", "div", "li"])
        if parent:
            paras = parent.find_all("p")
            for p in paras[:2]:
                t = p.get_text(" ", strip=True)
                if t and t != title and len(t) > 20:
                    desc = t[:160]
                    break
        if not desc:
            desc = title[:120]
        items.append(Item(title=title, link=link, description=desc))

    return items[:25]


def parse_nvidia(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/blog/"))


def parse_google_research(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/blog/"))


def parse_microsoft(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/engineering-at-microsoft/"))


def parse_figma(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/blog/"))


def parse_spotify(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/\d{4}/"))


def parse_slack(html: str, base_url: str) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "slack.engineering/" not in href:
            continue
        if any(x in href for x in ("/articles/page/", "/author/", "/tag/")):
            continue
        path = urlparse(href).path.strip("/")
        if not path or path == "articles":
            continue
        if href in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 15:
            continue
        seen.add(href)
        items.append(Item(title=title, link=href, description=title[:120]))
    if items:
        return items[:25]

    for match in re.finditer(
        r"\[([^\]]{15,})\]\((https://slack\.engineering/[^)]+/)\)",
        html,
    ):
        title, link = match.group(1), match.group(2)
        if "/articles/page/" in link or link in seen:
            continue
        seen.add(link)
        items.append(Item(title=title, link=link, description=title[:120]))
    return items[:25]


def parse_uber(html: str, base_url: str) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/blog/" not in href or "uber.com" not in href:
            continue
        if "/page/" in href or href.rstrip("/").endswith("/engineering"):
            continue
        path_parts = urlparse(href).path.strip("/").split("/")
        if len(path_parts) < 4:
            continue
        if href in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 15:
            continue
        seen.add(href)
        items.append(Item(title=title, link=href, description=title[:120]))
    if items:
        return items[:25]

    for match in re.finditer(
        r"\[([^\]]{15,})\]\((https://www\.uber\.com/[^)]+/blog/[^)]+/)\)",
        html,
    ):
        title, link = match.group(1), match.group(2)
        if "/page/" in link or link in seen:
            continue
        seen.add(link)
        items.append(Item(title=title, link=link, description=title[:120]))
    return items[:25]


def parse_stripe(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/blog/"))


def parse_discord(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/blog/"))


def parse_github(html: str, base_url: str) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()
    skip_titles = {
        "architecture & optimization",
        "engineering principles",
        "infrastructure",
        "platform security",
        "user experience",
        "learn more",
        "engineering",
    }
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "github.blog/engineering/" not in href:
            continue
        path_parts = urlparse(href).path.strip("/").split("/")
        if len(path_parts) < 3:
            continue
        if href in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 20 or title.lower() in skip_titles:
            continue
        seen.add(href)
        items.append(Item(title=title, link=href, description=title[:120]))
    if items:
        return items[:25]

    for match in re.finditer(
        r"\[([^\]]{15,})\]\((https://github\.blog/engineering/[^)]+/)\)",
        html,
    ):
        title, link = match.group(1), match.group(2)
        if "/page/" in link or link in seen:
            continue
        if title.lower() in skip_titles:
            continue
        seen.add(link)
        items.append(Item(title=title, link=link, description=title[:120]))
    return items[:25]


def parse_cloudflare(html: str, base_url: str) -> list[Item]:
    soup = BeautifulSoup(html, "lxml")
    items: list[Item] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/") or href.startswith("/tag/") or href.startswith("/author/"):
            continue
        if href in ("/", "/page/2/"):
            continue
        link = urljoin(base_url, href)
        if link in seen:
            continue
        title = a.get_text(" ", strip=True)
        if not title or len(title) < 15:
            continue
        seen.add(link)
        items.append(Item(title=title, link=link, description=title[:120]))
    return items[:25]


def parse_hubspot(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/blog/"))


def parse_mongodb(html: str, base_url: str) -> list[Item]:
    return parse_blog_posts_generic(html, base_url, re.compile(r"/company/blog/"))


PARSERS = {
    "ieee": parse_ieee_cfp,
    "airbnb": parse_airbnb_tech,
    "nvidia": parse_nvidia,
    "google": parse_google_research,
    "microsoft": parse_microsoft,
    "figma": parse_figma,
    "spotify": parse_spotify,
    "slack": parse_slack,
    "uber": parse_uber,
    "stripe": parse_stripe,
    "discord": parse_discord,
    "github": parse_github,
    "cloudflare": parse_cloudflare,
    "hubspot": parse_hubspot,
    "mongodb": parse_mongodb,
}

TECH_PARSER_MAP = {
    "1": "nvidia",
    "2": "google",
    "4": "microsoft",
    "7": "figma",
    "9": "spotify",
    "10": "slack",
    "11": "uber",
    "12": "stripe",
    "13": "discord",
    "15": "github",
    "16": "cloudflare",
    "19": "hubspot",
    "22": "mongodb",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_track_file(path: Path, source_name: str, items: list[Item]) -> None:
    lines = [f"# {source_name}", ""]
    for item in items:
        lines.extend(
            [
                f"## {item.title}",
                f"- **Link**: {item.link}",
                f"- **Description**: {item.description}",
                f"- **First seen**: {TODAY}",
                "",
            ]
        )
    path.write_text("\n".join(lines))


def parse_existing_links(path: Path) -> set[str]:
    if not path.exists():
        return set()
    links = re.findall(r"- \*\*Link\*\*: (.+)", path.read_text())
    return set(links)


def scrape_source(source_type: str, source_id: str, name: str, url: str) -> list[Item]:
    html = fetch(url)
    if source_type == "cfp":
        if "airbnb" in url:
            return parse_airbnb_tech(html, url)
        return parse_ieee_cfp(html, url)
    parser_key = TECH_PARSER_MAP.get(source_id, "generic")
    parser = PARSERS.get(parser_key, parse_blog_posts_generic)
    return parser(html, url)


def is_conceptual_tech_post(item: Item) -> bool:
    text = f"{item.title} {item.description}".lower()
    if any(re.search(pat, text, re.I) for pat in TECH_SKIP_PATTERNS):
        return False
    return any(re.search(pat, text, re.I) for pat in TECH_INCLUDE_PATTERNS)


def compose_digest(
    cfp_items: list[Item],
    tech_items: list[Item],
    failures: list[tuple[str, str, str]],
    *,
    digest_date: str = TODAY,
    filtered_tech_count: int = 0,
) -> str:
    lines = [f"# MyRSS Daily — {digest_date}", ""]

    lines.append("## CFP updates")
    if cfp_items:
        for item in cfp_items:
            lines.extend([f"### {item.title}", item.link, item.description, ""])
    else:
        lines.extend(["_No new CFPs today._", ""])

    lines.append("## Tech reads")
    if tech_items:
        for item in tech_items:
            lines.extend([f"### {item.title}", item.link, item.description, ""])
    else:
        lines.extend(["_No new conceptual tech posts today._", ""])

    if failures:
        lines.extend(["---", "Scrape failures:"])
        for name, url, err in failures:
            lines.append(f"- {name} ({url}): {err}")

    if filtered_tech_count:
        lines.extend(
            [
                "",
                "---",
                "Note: "
                f"{filtered_tech_count} additional tech item"
                f"{'s were' if filtered_tech_count != 1 else ' was'} "
                "tracked but filtered out (product launches, game announcements, or release posts).",
            ]
        )

    return "\n".join(lines)


def digest_subject(digest_date: str, digest_count: int) -> str:
    subject = f"MyRSS Daily — {digest_date}"
    if digest_count:
        subject = f"{subject} ({digest_count} updates)"
    return subject


def outbox_path(digest_date: str, *, sent: bool = False) -> Path:
    flag = "sent" if sent else "off"
    return OUTBOX_DIR / f"{digest_date}.{flag}.md"


def parse_outbox_file(path: Path) -> tuple[str, str]:
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n\n?(.*)\Z", text, re.DOTALL)
    if not match:
        raise ValueError(f"Invalid outbox file format: {path.name}")
    frontmatter, body = match.group(1), match.group(2)
    subject_match = re.search(r"^subject:\s*(.+)$", frontmatter, re.M)
    if not subject_match:
        raise ValueError(f"Missing subject in outbox file: {path.name}")
    return subject_match.group(1).strip(), body.rstrip()


def write_outbox_file(digest_date: str, subject: str, body: str) -> Path:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    path = outbox_path(digest_date, sent=False)
    path.write_text(f"---\nsubject: {subject}\n---\n\n{body.rstrip()}\n")
    print(f"OUTBOX saved {path.name}")
    return path


def send_email(subject: str, body: str) -> str | None:
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("EMAIL skipped: RESEND_API_KEY not set", file=sys.stderr)
        return None

    resp = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "from": RESEND_FROM,
            "to": [DIGEST_TO],
            "subject": subject,
            "text": body,
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        print(f"EMAIL failed: {resp.text}", file=sys.stderr)
        return None

    email_id = resp.json().get("id")
    print(f"EMAIL sent id={email_id} to={DIGEST_TO} subject={subject!r}")
    return email_id


def mark_outbox_sent(path: Path) -> Path:
    digest_date = path.name.split(".", 1)[0]
    sent_path = outbox_path(digest_date, sent=True)
    path.rename(sent_path)
    print(f"OUTBOX marked sent {sent_path.name}")
    return sent_path


def send_outbox_file(path: Path) -> str | None:
    subject, body = parse_outbox_file(path)
    email_id = send_email(subject, body)
    if email_id:
        mark_outbox_sent(path)
    return email_id


def process_pending_outbox() -> int:
    OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    pending = sorted(OUTBOX_DIR.glob("*.off.md"))
    sent_count = 0
    for path in pending:
        print(f"OUTBOX retry {path.name}")
        if send_outbox_file(path):
            sent_count += 1
    return sent_count


def send_digest_email(
    cfp_items: list[Item],
    tech_items: list[Item],
    failures: list[tuple[str, str, str]],
    *,
    digest_date: str = TODAY,
    filtered_tech_count: int = 0,
) -> str | None:
    digest_count = len(cfp_items) + len(tech_items)
    subject = digest_subject(digest_date, digest_count)
    body = compose_digest(
        cfp_items,
        tech_items,
        failures if digest_count else [],
        digest_date=digest_date,
        filtered_tech_count=filtered_tech_count,
    )
    write_outbox_file(digest_date, subject, body)
    return send_outbox_file(outbox_path(digest_date, sent=False))


def main() -> int:
    pending_sent = process_pending_outbox()
    if pending_sent:
        print(f"OUTBOX delivered {pending_sent} pending digest(s)")

    failures: list[tuple[str, str, str]] = []
    new_items_for_email: dict[str, list[Item]] = {"cfp": [], "tech": []}
    changed = False

    for source_type, config_file in [("cfp", "cfp_urls.json"), ("tech", "tech_urls.json")]:
        sources = load_json(URLS_DIR / config_file)
        for source_id, meta in sources.items():
            name = meta["name"]
            url = meta["url"]
            track_path = TRACK_DIR / f"{source_type}-{source_id}.md"
            try:
                items = scrape_source(source_type, source_id, name, url)
            except Exception as exc:
                failures.append((name, url, str(exc)))
                print(f"FAIL {source_type}-{source_id} ({name}): {exc}", file=sys.stderr)
                continue

            if not track_path.exists():
                write_track_file(track_path, name, items)
                changed = True
                print(f"BASELINE {track_path.name}: {len(items)} items")
            else:
                existing = parse_existing_links(track_path)
                new_items = [i for i in items if i.link not in existing]
                if new_items:
                    with track_path.open("a") as f:
                        for item in new_items:
                            f.write(f"\n## {item.title}\n")
                            f.write(f"- **Link**: {item.link}\n")
                            f.write(f"- **Description**: {item.description}\n")
                            f.write(f"- **First seen**: {TODAY}\n")
                    new_items_for_email[source_type].extend(new_items)
                    changed = True
                    print(f"UPDATED {track_path.name}: +{len(new_items)} new")

    cfp_for_email = new_items_for_email["cfp"]
    tech_for_email = [i for i in new_items_for_email["tech"] if is_conceptual_tech_post(i)]
    filtered_tech = len(new_items_for_email["tech"]) - len(tech_for_email)
    digest_count = len(cfp_for_email) + len(tech_for_email)

    if digest_count:
        send_digest_email(
            cfp_for_email,
            tech_for_email,
            failures,
            filtered_tech_count=filtered_tech,
        )
    else:
        print("EMAIL skipped: no qualifying digest items")

    total_new = sum(len(v) for v in new_items_for_email.values())
    print(
        f"SUMMARY new_items={total_new} digest_items={digest_count} "
        f"tech_filtered={filtered_tech} changed={changed} failures={len(failures)}"
    )
    if failures:
        for name, url, err in failures:
            print(f"  - {name}: {err}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
