"""
note_quality.py -- editorial substance floor for daily Field Notes.

Deterministic on purpose. An LLM judge over-flags (elsewhere in this project it
false-positived on real 2024 rules and on ingested expansion content), and a
false SKIP silently loses a day of content. So instead of scoring 1-5 we assert
a few concrete substance checks; a note that fails is regenerated ONCE, stricter,
and only skipped if it still fails -- better a skipped day than a thin, generic post.

Catches reliably: truly thin notes, missing structure, no concrete specifics,
hedge-heavy filler. It does NOT judge subtle "well-formed but flat" prose -- that
needs semantic judgment, which we deliberately avoid here.

    problems = assess(body, min_words=90, require=["## Today's Action"],
                      concrete_re=re.compile(r"CVE-\\d{4}-\\d{4,7}|\\b\\d[\\d.,]*\\b"),
                      need_specifics=2)
    if problems: ...   # regenerate stricter, else skip
"""
import re

_HEDGE = re.compile(
    r"\b(it'?s important to note|in the world of|at the end of the day|"
    r"needless to say|as we all know|in today'?s landscape|ever[- ]evolving|"
    r"the fact of the matter|when it comes to|that being said|"
    r"it goes without saying|first and foremost)\b",
    re.I,
)


def _words(t):
    return re.findall(r"[A-Za-z0-9']+", t or "")


def assess(text, *, min_words=90, require=(), concrete_re=None, need_specifics=2):
    """Return a list of substance problems (empty list == passes the floor).

    min_words     thinness floor on the note body (word count).
    require       markers that MUST appear (section headers, an 'At the table:' line);
                  matched case-insensitively as substrings.
    concrete_re   regex whose DISTINCT matches count as concrete specifics
                  (CVE IDs, numbers, $ amounts, dice, on-chain addresses);
                  need at least `need_specifics` of them.
    """
    problems = []
    body = text or ""
    wc = len(_words(body))
    if wc < min_words:
        problems.append(f"too thin ({wc} words < {min_words})")

    low = body.lower()
    for marker in require:
        if str(marker).lower() not in low:
            problems.append(f"missing required element {marker!r}")

    if concrete_re is not None:
        distinct = {m.group(0).lower() for m in concrete_re.finditer(body)}
        if len(distinct) < need_specifics:
            problems.append(f"not specific enough ({len(distinct)} concrete refs < {need_specifics})")

    if len(_HEDGE.findall(body)) >= 2:
        problems.append("hedge/filler phrasing")

    return problems
