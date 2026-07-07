"""
Deterministic Resources section for Issues. Links are never LLM-generated:
the model declares which URLs it drew from (SOURCES line), and we keep only the
ones that were actually in the input set (any hallucinated URL is dropped).
"""

import re


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
