"""
Source registry + system-focus weighting for It's Already Written.

Beat = all of TTRPG, but selection WEIGHTS the user's systems (dnd5e, shadowdark,
dcc). That weighting is centralised here (SYSTEM_KEYWORDS + focus_match) so every
tier — Field Notes, RTFM, Issues — ranks the same way.
"""

import re

# --- RSS / Atom news feeds. Only the ones that return FRESH entries from CI.
# (verified 2026-07-06; dead/stale ones removed: Goodman 403, Rascal dead,
#  Arcane Library + Roll for Combat return only years-old posts.) ---
RSS_FEEDS = [
    ("EN World",     "https://www.enworld.org/ewr-porta/index.rss"),  # D&D/TTRPG news, fresh
    ("Sly Flourish", "https://slyflourish.com/index.xml"),
    ("Gnome Stew",   "https://gnomestew.com/feed/"),
    ("Tribality",    "https://www.tribality.com/feed/"),
]

# --- Social: dice.camp (the TTRPG Mastodon). Public tag RSS, CI-friendly, and
# each feed carries a strong built-in system signal. Replaces Reddit, which now
# 403s all datacenter IPs. (tag, attributed-system-or-None) ---
MASTODON_INSTANCE = "https://dice.camp"
MASTODON_TAGS = [
    ("dnd",        "dnd5e"),
    ("dnd5e",      "dnd5e"),
    ("shadowdark", "shadowdark"),
    ("dccrpg",     "dcc"),
    ("ttrpg",      None),
    ("osr",        None),
]

# --- Sources that need Bright Data (paid) — blocked for the free tier from CI.
# The scraper leaves these OFF; wire them via the Bright Data adapter at audit. ---
BRIGHTDATA_ENABLED = False
BLOCKED_FREE_SOURCES = {
    "reddit": ["DnD", "Shadowdark", "dccrpg", "osr", "rpg"],  # 403 from datacenter
    "kickstarter": 34,   # Tabletop Games category; discover JSON 403s
    "bluesky": ["shadowdark", "dccrpg", "dnd5e"],             # searchPosts 403
    "x_tiktok_youtube": [],  # Bright Data social when enabled
}

# --- System focus. Each system: (canonical, [regex-ready keyword patterns]) ---
# dcc keywords are deliberately strict — bare "dcc" is too ambiguous to match on.
SYSTEM_KEYWORDS = {
    "dnd5e": [
        r"\bd&d\b", r"\bdnd\b", r"dungeons\s*&?\s*and?\s*dragons",
        r"\b5e\b", r"\b5th edition\b", r"\bone ?d&d\b", r"\bonednd\b",
        r"wizards of the coast", r"\bwotc\b",
    ],
    "shadowdark": [
        r"\bshadowdark\b", r"arcane library", r"kelsey dionne", r"cursed scroll",
    ],
    "dcc": [
        r"dungeon crawl classics", r"\bdcc rpg\b", r"goodman games",
    ],
}
_COMPILED = {sys: [re.compile(p, re.I) for p in pats] for sys, pats in SYSTEM_KEYWORDS.items()}

# Source authority weight (0-1). Nudges ranking toward outlets we trust.
SOURCE_WEIGHT = {
    "The Arcane Library": 1.0, "Goodman Games": 1.0, "EN World": 0.9,
    "Sly Flourish": 0.85, "Rascal News": 0.8, "Gnome Stew": 0.7,
    "Tribality": 0.6, "Roll for Combat": 0.6,
}


def focus_match(text):
    """Return the list of user-systems mentioned in `text` (may be empty)."""
    text = text or ""
    return [sys for sys, pats in _COMPILED.items() if any(p.search(text) for p in pats)]
