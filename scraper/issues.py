"""
Weekly Issues roundup for It's Already Written.

Synthesizes the past 7 days of scraped TTRPG news/social into an IAW-structured
Issue and saves it to _drafts/ for human review (NOT auto-published, NOT tweeted).
System-weighted. Resources are deterministic (validated subset of input URLs).

Env: ANTHROPIC_API_KEY (unless DRY_RUN=1).
"""

import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import style
from resources import validate_sources, build_resources_section
from field_note import slugify

ROOT = Path(__file__).resolve().parent.parent
DRAFTS_DIR = ROOT / "_drafts"
DB_PATH = Path(__file__).parent / "articles.db"
ISSUE_TRACKER = Path(__file__).parent / "issue_number.txt"
MODEL = "claude-opus-4-8"


def next_issue_number():
    n = (int(ISSUE_TRACKER.read_text().strip()) + 1) if ISSUE_TRACKER.exists() else 1
    return n


def commit_issue_number(n):
    ISSUE_TRACKER.write_text(str(n))


def weeks_items(conn, limit=120):
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    # system-matched first (weighted), then general, both newest-first
    return conn.execute("""
        SELECT title, url, source, platform, system_tags, summary, published_at
        FROM articles
        WHERE published_at >= ? AND used_in_issue = 0
        ORDER BY (system_tags != '') DESC, score DESC
        LIMIT ?
    """, (since, limit)).fetchall()


def mark_used(conn, urls):
    for u in urls:
        conn.execute("UPDATE articles SET used_in_issue = 1 WHERE url = ?", (u,))
    conn.commit()


def build_prompt(items):
    lines = []
    for title, url, source, platform, systics, summary, pub in items:
        tag = f" [{systics}]" if systics else ""
        lines.append(f"[{platform}] {pub[:10]} | {source}{tag}\nTitle: {title}\nURL: {url}\nSummary: {summary}\n")
    body = "\n---\n".join(lines)
    return f"""You are the anonymous editor of "It's Already Written." — a weekly tabletop RPG intelligence digest, the RTFM entry in a family of dry, authoritative, source-cited digests. You cover all of TTRPG but weight your own systems (D&D 5e, Shadowdark, Dungeon Crawl Classics). Voice: world-weary, precise, allergic to hype and hobby drama. You read the rulebook, not the discourse.

Below are this week's scraped TTRPG items (news, blog posts, and social). Write the weekly Issue in Markdown.

Use exactly these section headers (## ...), in order:
1. **This Week's Verdict** — 2 to 3 sentences capturing the week's theme with dry wit.
2. **Releases & Announcements** — new books, products, and official news. Name the products and publishers.
3. **Rules & Errata** — official rules changes, errata, and clarifications. Weight D&D 5e, Shadowdark, DCC.
4. **The Community** — notable discourse, arguments, and posts worth knowing about.
5. **On the Horizon** — crowdfunding, previews, and upcoming releases.

Rules:
- Be specific: name products, publishers, systems, and people. Bold the named entities.
- Mix prose and short lists naturally, no bullet-point soup.
- Under 1100 words. Do NOT write a Resources or Sources section (appended automatically).
- If a claim cannot be tied to one of the items below, leave it out.
- A section with nothing real to report gets one dry sentence saying so, not filler.
- Do not mention that AI wrote this. Do not use em or en dashes.
- Ban: delve, tapestry, testament to, dive in, unleash, moreover, furthermore.

Output format:
- FIRST line: "SUMMARY: <one dry sentence for the blog index>"
- Then the post body (the five sections).
- LAST line: "SOURCES: <comma-separated URLs, verbatim from the items below, of the ones you actually drew from>"

---

THIS WEEK'S ITEMS:

{body}
"""


def parse(raw):
    summary, sources_line, body = "", "", []
    for line in raw.splitlines():
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "", 1).strip()
        elif line.startswith("SOURCES:"):
            sources_line = line
        else:
            body.append(line)
    return summary, sources_line, "\n".join(body).strip()


def write_draft(issue_number, summary, body, sources):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week = datetime.now(timezone.utc).strftime("Week of %B %d, %Y")
    fname = DRAFTS_DIR / f"{today}-issue-{issue_number:03d}.md"
    title = f"Issue #{issue_number:03d} — {week}"   # em dash allowed in structural titles
    body = body + "\n\n" + build_resources_section(sources)
    fm = (
        "---\n"
        "layout: post\n"
        f'title: "{title}"\n'
        f"date: {today}\n"
        "category: issues\n"
        "tier: issues\n"
        f'issue: "{issue_number}"\n'
        f'summary: "{summary.replace(chr(34), chr(39))}"\n'
        "---\n\n"
    )
    DRAFTS_DIR.mkdir(exist_ok=True)
    fname.write_text(fm + body + "\n", encoding="utf-8")
    print(f"Wrote DRAFT {fname.relative_to(ROOT)} (review before publishing)")
    return fname


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    if not DB_PATH.exists():
        print("No articles.db; run the scraper first.")
        return
    conn = sqlite3.connect(DB_PATH)
    items = weeks_items(conn)
    if len(items) < 5:
        print(f"Only {len(items)} items this week; too thin for an Issue. Skipping.")
        conn.close()
        return
    print(f"Building Issue from {len(items)} items...")
    prompt = build_prompt(items)
    if dry:
        print("\n--- DRY RUN: prompt (truncated) ---\n" + prompt[:1500])
        conn.close()
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: set ANTHROPIC_API_KEY (or DRY_RUN=1)")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def generate(p):
        r = client.messages.create(model=MODEL, max_tokens=2200,
                                   messages=[{"role": "user", "content": p}])
        return parse(r.content[0].text.strip())

    summary, sources_line, body = generate(prompt)
    input_urls = [it[1] for it in items]

    summary, body = style.normalize(summary), style.normalize(body)
    if style.lint(f"{summary}\n{body}"):
        tells = style.lint(f"{summary}\n{body}")
        print(f"AI tells {tells}; regenerating once.")
        strict = prompt + f"\n\nYour previous draft used banned tells ({', '.join(tells)}). Rewrite avoiding all of them and any em/en dashes."
        summary, sources_line, body = generate(strict)
        summary, body = style.normalize(summary), style.normalize(body)
        if style.lint(f"{summary}\n{body}"):
            print("WARNING: residual tells after retry (flag for review)")

    if not body:
        print("Empty generation; skipping.")
        conn.close()
        return

    sources = validate_sources(sources_line, input_urls)
    issue_number = next_issue_number()
    write_draft(issue_number, summary, body, sources)
    commit_issue_number(issue_number)
    mark_used(conn, sources or input_urls)   # mark what we drew from (or all, if none declared)
    conn.close()


if __name__ == "__main__":
    main()
