"""
Source citations. We NEVER deep-link individual rules facts (high dead-link risk
and the SRDs/PDFs don't have stable per-fact URLs). Instead:
  - rules-atom notes cite the system's canonical, stable source page + cross-link
    the companion YouTube short (guaranteed valid, from the atom itself);
  - news notes cite the original article URL (the real, live link).
This keeps every source verifiable and avoids hallucinated links.
"""

# Curated, stable per-system landing pages (not generated, not deep links).
SYSTEM_SOURCE = {
    "dnd5e":      ("D&D 5e SRD 5.2.1 (Creative Commons)",   "https://www.dndbeyond.com/srd"),
    "shadowdark": ("Shadowdark RPG — The Arcane Library",   "https://www.thearcanelibrary.com/pages/shadowdark"),
    "dcc":        ("Dungeon Crawl Classics RPG — Goodman Games", "https://goodman-games.com/dungeon-crawl-classics-rpg/"),
}


def _yaml_list(sources):
    """sources: list of (title, url) -> Jekyll front-matter YAML block."""
    lines = ["sources:"]
    for title, url in sources:
        safe = title.replace('"', "'")
        lines.append(f'  - title: "{safe}"')
        lines.append(f'    url: "{url}"')
    return "\n".join(lines)


def atom_sources(system, youtube_url=""):
    src = []
    if system in SYSTEM_SOURCE:
        src.append(SYSTEM_SOURCE[system])
    if youtube_url:
        src.append(("Companion short (Bizzal Games)", youtube_url))
    return src


def news_sources(article_url, source_name, system=""):
    src = [(source_name or "Source", article_url)]
    if system in SYSTEM_SOURCE:      # add the rules reference the note leans on
        src.append(SYSTEM_SOURCE[system])
    return src


def yaml_block(sources):
    return _yaml_list(sources)
