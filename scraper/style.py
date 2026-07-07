"""
Deterministic AI-tell guard for It's Already Written.

The family content rule (no em dashes, no AI-authorship mention, deterministic
source links) is enforced in CODE here, not just requested in the prompt, so a
tell can't reach the site even if the model backslides. normalize() fixes
punctuation unconditionally; lint() reports surviving word/phrase tells so the
generator can force one stricter retry.
"""

import re

# --- unconditional punctuation fixes (the classic typographic AI tells) ---
def normalize(text):
    if not text:
        return text
    text = text.replace("—", ", ")   # em dash  -> comma
    text = text.replace("–", "-")     # en dash  -> hyphen
    text = text.replace("‘", "'").replace("’", "'")   # curly single
    text = text.replace("“", '"').replace("”", '"')   # curly double
    text = text.replace("…", "...")   # ellipsis char
    text = re.sub(r"\s+,", ",", text)      # tidy artifacts from em-dash swap
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text

# --- high-confidence lexical/phrase tells (kept tight to avoid flagging
#     legitimate TTRPG prose like "realm", "unlock a spell", etc.) ---
AI_TELLS = [
    r"\bdelve\b", r"\btapestry\b", r"\btestament to\b",
    r"\bin the world of\b", r"\bit'?s important to note\b", r"\bit'?s worth noting\b",
    r"\bat the end of the day\b", r"\bwhen it comes to\b",
    r"\bnavigat\w+ the\b", r"\bever[- ]evolving\b", r"\bin today'?s\b",
    r"\bgame[- ]?changer\b", r"\bwhether you'?re\b",
    r"\bnot only\b[^.]*\bbut also\b", r"\bdive in\b", r"\bunleash\b",
    r"\bfoster\b", r"\bmoreover\b", r"\bfurthermore\b", r"\bin conclusion\b",
    r"\brich (history|tapestry|tradition|lore)\b",
]
_COMPILED = [re.compile(p, re.I) for p in AI_TELLS]


def lint(text):
    """Return the list of surviving tells (should be empty after normalize+retry)."""
    if not text:
        return []
    hits = []
    if "—" in text or "–" in text:
        hits.append("dash char")
    for p in _COMPILED:
        m = p.search(text)
        if m:
            hits.append(m.group(0).strip())
    return sorted(set(hits))
