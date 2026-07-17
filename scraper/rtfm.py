"""
Weekly RTFM deep-dive for It's Already Written.

Clusters 3-5 unused atoms that share a category (rotating across systems) and
synthesizes them into one source-cited deep dive in the RTFM voice, optionally
enriched with current discourse on the topic from the scrape. Auto-publishes to
_posts/ (tier: rtfm). Reuses the AI-tell + fidelity guards from field_note.

Env: ANTHROPIC_API_KEY (unless DRY_RUN=1).
"""

import os
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

import registries
import sources as src
import style
from field_note import parse_response, slugify, significant_words
from resources import build_related_section

ROOT = Path(__file__).resolve().parent.parent
POSTS_DIR = ROOT / "_posts"
DB_PATH = Path(__file__).parent / "articles.db"
STATE_PATH = Path(__file__).parent / "state" / "published_rtfm.json"
MODEL = "claude-opus-4-8"
ROTATION = ["dnd5e", "shadowdark", "dcc"]
MIN_CLUSTER = 3
MAX_CLUSTER = 5


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"used_fact_pks": [], "last_system": ""}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def pick_cluster(state):
    """Rotate systems; in the first with a category holding >= MIN_CLUSTER unused
    atoms, return (system, category, atoms[:MAX])."""
    pools = registries.all_facts()
    used = set(state["used_fact_pks"])
    start = ROTATION.index(state["last_system"]) + 1 if state["last_system"] in ROTATION else 0
    for i in range(len(ROTATION)):
        system = ROTATION[(start + i) % len(ROTATION)]
        by_cat = defaultdict(list)
        for f in pools.get(system, []):
            if f["fact_pk"] not in used:
                by_cat[f["category"]].append(f)
        cats = sorted(by_cat.items(), key=lambda kv: len(kv[1]), reverse=True)
        if cats and len(cats[0][1]) >= MIN_CLUSTER:
            category, atoms = cats[0]
            return system, category, atoms[:MAX_CLUSTER]
    return None, None, None


def discourse(system, limit=3):
    """A few recent high-signal scraped items on this system, for current context."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    since = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    rows = conn.execute("""
        SELECT title, source, url FROM articles
        WHERE published_at >= ? AND system_tags LIKE ?
        ORDER BY score DESC LIMIT ?
    """, (since, f"%{system}%", limit)).fetchall()
    conn.close()
    return rows


def humanize(category):
    return category.replace("_", " ").title()


def build_prompt(system, category, atoms, context):
    facts = "\n".join(
        f"- {a['fact_name']} ({a['fact_kind']}): {a['hook']} {a['body']}" for a in atoms)
    ctx = ""
    if context:
        ctx = "\n\nCurrent discourse you MAY reference for framing (optional, only if relevant):\n" + \
              "\n".join(f"- {t} ({s})" for t, s, _ in context)
    names = ", ".join(a["fact_name"] for a in atoms)
    return f"""You are the anonymous editor of "It's Already Written." — the RTFM entry in a family of dry, authoritative, source-cited digests. You actually read the book.

Write an "RTFM" deep dive: a mid-week piece that synthesizes several related rules facts into one coherent lesson. Theme: {humanize(category)} in {system}.

Cover ALL of these facts by their EXACT names (do not rename or reclassify any of them): {names}

Source material (reshape into editorial prose, do not quote verbatim):
{facts}{ctx}

Structure the body as:
- An opening that frames why {humanize(category)} matters at the table.
- The synthesis: weave the specific facts together into the actual lesson, naming each one.
- A closing "**Running it:**" line with one concrete piece of advice.

Rules:
- 450 to 700 words. Substantive, not padded.
- Name every fact accurately; a Bugbear is not a Goblin.
- No hype, no filler. Do NOT use em dashes or en dashes.
- Ban: delve, tapestry, testament to, dive in, unleash, moreover, furthermore, "it's important to note".
- Do not mention that AI wrote this.

Output EXACTLY:
TITLE: <short punchy title naming the theme>
SUMMARY: <one dry sentence for the blog index>
BODY:
<the deep dive>
"""


def build_sources(system, atoms):
    out = []
    if system in src.SYSTEM_SOURCE:
        out.append(src.SYSTEM_SOURCE[system])
    for a in atoms:
        if a.get("youtube_url"):
            out.append((f"Companion short: {a['fact_name']}", a["youtube_url"]))
    return out


def facts_covered(atoms, body):
    """Soft fidelity: every clustered fact should be named in the deep dive."""
    missing = []
    low = body.lower()
    for a in atoms:
        words = significant_words(a["fact_name"])
        if words and not any(w.lower() in low for w in words):
            missing.append(a["fact_name"])
    return missing


def write_post(system, category, atoms, title, summary, body):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(title or f"rtfm-{category}")
    fname = POSTS_DIR / f"{today}-{slug}.md"
    src_list = build_sources(system, atoms)
    fm = (
        "---\n"
        "layout: post\n"
        f'title: "{(title or "RTFM").replace(chr(34), chr(39))}"\n'
        f"date: {today}\n"
        f"category: {category}\n"
        f"system: {system}\n"
        "tier: rtfm\n"
        f'summary: "{summary.replace(chr(34), chr(39))}"\n'
        f"{src.yaml_block(src_list)}\n"
        "---\n\n"
    )
    related = build_related_section(POSTS_DIR, fname.name)
    POSTS_DIR.mkdir(exist_ok=True)
    fname.write_text(
        fm + body + ("\n\n" + related if related else "") + "\n", encoding="utf-8"
    )
    print(f"Wrote {fname.relative_to(ROOT)}")
    return fname


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    state = load_state()
    system, category, atoms = pick_cluster(state)
    if not atoms:
        print(f"No category has {MIN_CLUSTER}+ unused atoms. Skipping RTFM this week.")
        return
    print(f"Cluster: {system}/{category} -> {[a['fact_name'] for a in atoms]}")
    prompt = build_prompt(system, category, atoms, discourse(system))
    if dry:
        print("\n--- DRY RUN: prompt ---\n" + prompt)
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ERROR: set ANTHROPIC_API_KEY (or DRY_RUN=1)")
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    def generate(p):
        r = client.messages.create(model=MODEL, max_tokens=1600,
                                   messages=[{"role": "user", "content": p}])
        return parse_response(r.content[0].text.strip())

    title, summary, body = generate(prompt)
    if not body:
        print("Empty generation; skipping.")
        return
    title, summary, body = (style.normalize(x) for x in (title, summary, body))

    problems = []
    tells = style.lint(f"{title}\n{summary}\n{body}")
    if tells:
        problems.append(f"banned AI tells ({', '.join(tells)})")
    missing = facts_covered(atoms, body)
    if missing:
        problems.append(f"these facts were not named: {', '.join(missing)}")
    if problems:
        print(f"Draft issues {problems}; regenerating once.")
        strict = prompt + ("\n\nYour previous draft had these problems: "
                           f"{'; '.join(problems)}. Fix ALL of them, no em/en dashes.")
        t2, s2, b2 = generate(strict)
        if b2:
            title, summary, body = (style.normalize(x) for x in (t2, s2, b2))
        if style.lint(f"{title}\n{summary}\n{body}") or facts_covered(atoms, body):
            print("WARNING: residual issues after retry (flag for audit)")

    write_post(system, category, atoms, title, summary, body)
    state["used_fact_pks"].extend(a["fact_pk"] for a in atoms)
    state["last_system"] = system
    save_state(state)


if __name__ == "__main__":
    main()
