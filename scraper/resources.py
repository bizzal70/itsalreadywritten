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


def _post_title(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'^title:\s*"(.+?)"', text, re.M)
    return m.group(1) if m else None


def build_related_section(posts_dir, current_filename: str, limit: int = 3) -> str:
    """Link the `limit` most recent prior posts plus the section indexes.

    Deterministic: reads the actual files on disk, so no URL is ever invented.
    The current post isn't written to disk yet when this runs, so the scan only
    sees earlier posts; `current_filename` is excluded as a re-run safeguard.
    Returns "" if there are no prior posts (a brand-new blog).
    """
    posts_dir = Path(posts_dir)
    try:
        files = sorted(
            (p for p in posts_dir.glob("*.md") if p.name != current_filename),
            key=lambda p: p.name,
            reverse=True,
        )
    except OSError:
        files = []

    lines, picked = [], 0
    for p in files:
        url = _post_url(p.name)
        if not url:
            continue
        title = _post_title(p) or p.stem[11:].replace("-", " ").strip().capitalize()
        lines.append(f"- [{title}]({url})")
        picked += 1
        if picked >= limit:
            break
    if not lines:
        return ""

    out = ["## Related", ""]
    out += lines
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
