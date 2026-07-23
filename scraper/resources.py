"""
Deterministic Resources section for Issues. Links are never LLM-generated:
the model declares which URLs it drew from (SOURCES line), and we keep only the
ones that were actually in the input set (any hallucinated URL is dropped).

Also builds the deterministic internal-linking "Related" section — recent prior
posts plus the section indexes — so a reader has a path deeper into the site
instead of dead-ending after the sources.
"""

import re
from pathlib import Path

# GitHub Pages baseurl for this blog. Hardcoded (not `{{ site.baseurl }}`) so the
# links don't depend on Liquid being rendered inside post bodies.
_BASEURL = "/itsalreadywritten"
_FNAME_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})-(.+)\.md$")


def _post_url(filename: str) -> str | None:
    """`YYYY-MM-DD-slug.md` -> `/baseurl/YYYY/MM/DD/slug/` (permalink /:y/:m/:d/:title/)."""
    m = _FNAME_RE.match(filename)
    if not m:
        return None
    y, mo, d, slug = m.groups()
    return f"{_BASEURL}/{y}/{mo}/{d}/{slug}/"


# --- topical "Related" ranking -------------------------------------------------
# Related used to be the 3 most-RECENT posts, which dead-ends readers on unrelated
# content. Now prior posts are ranked by keyword overlap with the current post
# (shared TITLE terms weighted), with recency only as a tiebreaker and to
# back-fill so the section is never short. For this blog the caller prepends the
# post's `system` (dnd5e/shadowdark/dcc) to current_text, so same-system posts
# rank together. Deterministic: reads real files.
_STOP = set(
    "the a an and or of to in on at for is are was were be been by from as with "
    "that this it its you your their they them we our not but if how why what "
    "which when while then than into about over after before more most some any "
    "all can will just like one two new today week weekly daily field note notes "
    "issue rtfm read follow subscribe rss related resources here there also only "
    "very much many made make using used".split()
)
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _keywords(text: str) -> dict:
    text = _MD_LINK.sub(r"\1", text or "")          # keep link text, drop URLs
    text = re.sub(r"`[^`]*`", " ", text)            # drop code spans
    out: dict = {}
    for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-']{2,}", text.lower()):
        w = w.strip("-'")
        if len(w) < 3 or w in _STOP:
            continue
        out[w] = out.get(w, 0) + 1
    return out


def _relevance(cur: dict, cand_title: str, cand_body: str) -> int:
    cb = _keywords(cand_body)
    for t in set(_keywords(cand_title)):
        cb[t] = cb.get(t, 0) + 2                     # a shared TITLE term counts more
    return sum(cb.get(t, 0) for t in cur if t in cb)


def _post_text(path: Path):
    """(title, body) for a post file; body is the markdown minus front-matter.
    The front-matter `system:` is folded into the body so it counts as a keyword."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return "", ""
    m = re.search(r'^title:\s*"(.+?)"', text, re.M)
    title = m.group(1) if m else ""
    sysm = re.search(r'^system:\s*(\S+)', text, re.M)
    body = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    if sysm:
        body = f"{sysm.group(1)} {body}"
    return title, body


def build_related_section(posts_dir, current_filename: str, limit: int = 3,
                          current_text: str = "") -> str:
    """Link the `limit` most RELEVANT prior posts plus the section indexes.

    Ranked by keyword overlap with `current_text` (the post being written);
    recency is the tiebreaker and back-fill. With no `current_text` this reduces
    to the old most-recent behavior. Deterministic: reads real files on disk, so
    no URL is ever invented. `current_filename` is excluded as a re-run safeguard.
    """
    posts_dir = Path(posts_dir)
    cur = _keywords(current_text)
    try:
        files = [p for p in posts_dir.glob("*.md") if p.name != current_filename]
    except OSError:
        files = []

    entries = []  # (score, filename_sortkey, url, title)
    for p in files:
        url = _post_url(p.name)
        if not url:
            continue
        title, body = _post_text(p)
        title = title or p.stem[11:].replace("-", " ").strip().capitalize()
        score = _relevance(cur, title, body) if cur else 0
        entries.append((score, p.name, url, title))

    if not entries:
        return ""
    entries.sort(key=lambda e: (e[0], e[1]), reverse=True)
    picked = entries[:limit]

    out = ["## Related", ""]
    out += [f"- [{t}]({u})" for _, _, u, t in picked]
    out += [
        "",
        f"More: [Latest]({_BASEURL}/) · [Issues]({_BASEURL}/issues/) · [RTFM]({_BASEURL}/rtfm/)",
    ]
    return "\n".join(out) + "\n"


def validate_sources(declared_line, input_urls):
    """Keep only declared source URLs that were actually in the input set."""
    if not declared_line:
        return []
    raw = declared_line.replace("SOURCES:", "", 1)
    candidates = [u.strip().strip(",") for u in re.split(r"[\s,]+", raw) if u.strip()]
    inset = set(input_urls)
    seen, out = set(), []
    for u in candidates:
        if u in inset and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def build_resources_section(source_urls, heading="## Resources"):
    lines = [f"{heading}\n"]
    for url in source_urls:
        lines.append(f"- {url}")
    return "\n".join(lines) + "\n"
