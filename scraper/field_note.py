"""
Daily Field Note generator for It's Already Written.

Picks the single best-signal item across two streams — a rules atom (dnd5e /
shadowdark / dcc) or a scraped news beat — WEIGHTED toward the user's systems,
lightly rewrites it into the "It's Already Written" RTFM voice via Claude, and
writes a source-cited Jekyll post to _posts/.

Default behaviour: a rules atom (curated, reliable), rotating across systems.
A news beat only wins when it's genuinely high-signal AND fresh (a real event),
which keeps the feed system-focused instead of chasing hobby noise.

Env: ANTHROPIC_API_KEY (required unless DRY_RUN=1). DRY_RUN=1 skips Claude + write.
"""

import os
import re
import json
import sqlite3
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

import registries
import sources as src
import style

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "_posts"
DB_PATH = Path(__file__).parent / "articles.db"
STATE_PATH = Path(__file__).parent / "state" / "published_fieldnotes.json"
MODEL = "claude-opus-4-8"

ROTATION = ["dnd5e", "shadowdark", "dcc"]
NEWS_WIN_SCORE = 4.0      # a news beat must clear this to beat a rules atom
NEWS_MAX_AGE_H = 48       # ...and be this fresh


# ---------------- state ----------------
def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"used_fact_pks": [], "used_article_urls": [], "last_system": ""}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------- selection ----------------
def pick_atom(state):
    """Next system after last_system (round-robin) that has an unused fact."""
    pools = registries.all_facts()
    used = set(state["used_fact_pks"])
    start = ROTATION.index(state["last_system"]) + 1 if state["last_system"] in ROTATION else 0
    for i in range(len(ROTATION)):
        system = ROTATION[(start + i) % len(ROTATION)]
        pool = [f for f in pools.get(system, []) if f["fact_pk"] not in used]
        if pool:
            return pool[0]     # newest unused (facts_for returns newest-first)
    return None


def pick_news(state):
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    since = (datetime.now(timezone.utc) - timedelta(hours=NEWS_MAX_AGE_H)).isoformat()
    rows = conn.execute("""
        SELECT url, source, title, summary, system_tags, score, published_at
        FROM articles
        WHERE used_in_fieldnote = 0 AND system_tags != '' AND published_at >= ?
        ORDER BY score DESC LIMIT 20
    """, (since,)).fetchall()
    conn.close()
    used = set(state["used_article_urls"])           # persisted across runs
    row = next((r for r in rows if r[0] not in used), None)
    if not row:
        return None
    url, source, title, summary, systics, score, pub = row
    return {"url": url, "source": source, "title": title, "summary": summary,
            "system": systics.split(",")[0], "score": score}


def choose(state):
    """Return ('atom'|'news', payload). Best-signal, system-weighted."""
    news = pick_news(state)
    if news and news["score"] >= NEWS_WIN_SCORE:
        return "news", news
    atom = pick_atom(state)
    if atom:
        return "atom", atom
    if news:                       # atoms exhausted; fall back to best news
        return "news", news
    return None, None


# ---------------- prompts ----------------
VOICE = (
    'You are the anonymous editor of "It\'s Already Written." — the RTFM entry in '
    'a family of dry, authoritative, source-cited digests (its siblings cover cyber '
    'and crypto). Voice: world-weary, precise, faintly amused, deeply rules-literate. '
    'You actually read the book. You never hype, never pad, never hedge.'
)

RULES = (
    "Rules:\n"
    "- Under 220 words. Tight.\n"
    "- Name the system, the rule/creature/spell/item, and the specific mechanic.\n"
    "- No hype, no filler, no second-person life-coaching.\n"
    "- Be exact about identity. Use the fact's real name; NEVER rename or "
    "reclassify it (a Bugbear is not a Goblin, Counterspell is not 'a spell'). "
    "The TITLE must name the actual subject, not a different creature/thing.\n"
    "- Do NOT use em dashes or en dashes. Use periods, commas, or parentheses.\n"
    "- Ban this LLM-tell vocabulary: delve, tapestry, testament to, dive in, "
    "unleash, foster, moreover, furthermore, 'it's important to note', 'in the "
    "world of', 'whether you're', 'not only... but also', 'ever-evolving'.\n"
    "- Do not mention that AI wrote this.\n\n"
    "Output EXACTLY:\n"
    "TITLE: <short punchy noun phrase, no system prefix>\n"
    "SUMMARY: <one dry sentence for the blog index>\n"
    "BODY:\n"
    "<2-3 tight paragraphs, then a final line starting '**At the table:** ' with one concrete play>"
)


def atom_prompt(a):
    return f"""{VOICE}

Write a daily "Field Note": one rules fact, sharpened into the house voice.

System: {a['system']}
Fact: {a['fact_name']} ({a['fact_kind']}, category: {a['category']}, angle: {a['angle']})

Raw material already drafted for a short video (reshape into editorial prose, do
not quote verbatim):
HOOK: {a['hook']}
BODY: {a['body']}
CTA: {a['cta']}

{RULES}
"""


def news_prompt(nw):
    return f"""{VOICE}

Write a daily "Field Note" reacting to one piece of TTRPG news with a rules-literate,
source-first lens. Say what happened, then what it means for people who run games.

System focus: {nw['system']}
Headline: {nw['title']}
Source: {nw['source']}
Summary: {nw['summary']}

{RULES}
"""


# ---------------- render ----------------
def slugify(text):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:60] or "field-note"


_TITLE_STOP = {"the", "and", "for", "with", "that", "this"}


def significant_words(name):
    return [w for w in re.findall(r"[A-Za-z]+", name or "")
            if len(w) > 3 and w.lower() not in _TITLE_STOP]


def title_faithful(fact_name, title):
    """The title must name the actual subject (guards against Claude renaming a
    Bugbear Stalker to 'Goblin'). True if any significant fact word is present."""
    words = significant_words(fact_name)
    if not words:
        return True
    return any(w.lower() in (title or "").lower() for w in words)


def parse_response(raw):
    title = summary = ""
    body = []
    mode = None
    for line in raw.splitlines():
        if line.startswith("TITLE:"):
            title = line[6:].strip()
        elif line.startswith("SUMMARY:"):
            summary = line[8:].strip()
        elif line.startswith("BODY:"):
            mode = "body"
        elif mode == "body":
            body.append(line)
    return title, summary, "\n".join(body).strip()


def write_post(kind, payload, title, summary, body):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    system = payload["system"]
    if kind == "atom":
        category = payload["category"] or "rules"
        source_list = src.atom_sources(system, payload.get("youtube_url", ""))
    else:
        category = "news"
        source_list = src.news_sources(payload["url"], payload["source"], system)

    slug = slugify(title or payload.get("fact_name", "field-note"))
    fname = POSTS_DIR / f"{today}-{slug}.md"
    fm = (
        "---\n"
        "layout: post\n"
        f'title: "{(title or "Field Note").replace(chr(34), chr(39))}"\n'
        f"date: {today}\n"
        f"category: {category}\n"
        f"system: {system}\n"
        "tier: field-notes\n"
        f'summary: "{summary.replace(chr(34), chr(39))}"\n'
        f"{src.yaml_block(source_list)}\n"
        "---\n\n"
    )
    cta = (
        "\n\n---\n\n*Daily field notes, weekly Issues. Follow "
        "[@ItsAlrdyWritten](https://x.com/ItsAlrdyWritten) or subscribe via RSS.*"
    )
    POSTS_DIR.mkdir(exist_ok=True)
    fname.write_text(fm + body + cta + "\n", encoding="utf-8")
    print(f"Wrote {fname.relative_to(ROOT)}")
    return fname


def mark_used(kind, payload, state):
    if kind == "atom":
        state["used_fact_pks"].append(payload["fact_pk"])
        state["last_system"] = payload["system"]
    else:
        state["used_article_urls"].append(payload["url"])
        if DB_PATH.exists():
            conn = sqlite3.connect(DB_PATH)
            conn.execute("UPDATE articles SET used_in_fieldnote=1 WHERE url=?", (payload["url"],))
            conn.commit()
            conn.close()
    save_state(state)


def git_push(path):
    subprocess.run(["git", "add", str(path)], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-m", f"Field Note {path.stem}"], cwd=ROOT, check=True)
    subprocess.run(["git", "push"], cwd=ROOT, check=True)


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    state = load_state()
    kind, payload = choose(state)
    if not kind:
        print("Nothing to publish (atoms exhausted, no fresh news). Skipping.")
        return

    prompt = atom_prompt(payload) if kind == "atom" else news_prompt(payload)
    label = payload.get("fact_name") or payload.get("title", "")
    print(f"Selected [{kind}] system={payload['system']}: {label[:60]}")

    if dry:
        print("\n--- DRY RUN: prompt ---\n")
        print(prompt)
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: set ANTHROPIC_API_KEY (or DRY_RUN=1)")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def generate(p):
        resp = client.messages.create(
            model=MODEL, max_tokens=900,
            messages=[{"role": "user", "content": p}],
        )
        return parse_response(resp.content[0].text.strip())

    title, summary, body = generate(prompt)
    if not body:
        print("Empty generation; skipping.")
        return

    # deterministic guards (enforced in code, not just prompt): normalize
    # punctuation + AI-tell lint + title-fidelity, then ONE stricter retry.
    def check(t, s, b):
        problems = []
        tells = style.lint(f"{t}\n{s}\n{b}")
        if tells:
            problems.append(f"banned AI tells ({', '.join(tells)})")
        if kind == "atom" and not title_faithful(payload["fact_name"], t):
            problems.append(f"the TITLE must name '{payload['fact_name']}' and must "
                            "not rename or reclassify it")
        return problems

    title, summary, body = (style.normalize(x) for x in (title, summary, body))
    problems = check(title, summary, body)
    if problems:
        print(f"Draft issues {problems}; regenerating once, stricter.")
        strict = prompt + ("\n\nYour previous draft had these problems: "
                           f"{'; '.join(problems)}. Fix ALL of them and avoid any "
                           "em/en dashes.")
        t2, s2, b2 = generate(strict)
        if b2:
            title, summary, body = (style.normalize(x) for x in (t2, s2, b2))
        problems = check(title, summary, body)
        if problems:
            print(f"WARNING: residual issues after retry: {problems}")
            # last-resort accuracy net: never ship a title that misnames the fact
            if kind == "atom" and not title_faithful(payload["fact_name"], title):
                title = payload["fact_name"]
                print(f"  forced title to fact name: {title}")

    path = write_post(kind, payload, title, summary, body)
    mark_used(kind, payload, state)
    if not os.environ.get("GITHUB_ACTIONS"):
        git_push(path)


if __name__ == "__main__":
    main()
