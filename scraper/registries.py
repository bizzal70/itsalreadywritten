"""
Rules-atom stream: reads the published registries from Bizzal-Games-YT-PUB
(public raw, per the remote-only rule for that repo) and normalises each atom
into a flat fact record. Dedups by fact_pk so the same fact's multiple script
takes collapse to one.
"""

import json
import urllib.request

SYSTEMS = ["dnd5e", "shadowdark", "dcc"]
RAW = ("https://raw.githubusercontent.com/bizzal70/Bizzal-Games-YT-PUB/main/"
       "data/state/published_registry_{system}.json")
UA = "iaw-registries/1.0"


def _fetch(system):
    url = RAW.format(system=system)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    return data.get("items", data) if isinstance(data, dict) else data


def facts_for(system):
    """Return deduped fact records (newest-first) for one system."""
    seen, out = set(), []
    items = _fetch(system)
    # newest first so the take we keep is the most recent one
    items = sorted(items, key=lambda it: it.get("day", ""), reverse=True)
    for it in items:
        fp = it.get("fingerprint", {})
        pk = fp.get("fact_pk")
        if not pk or pk in seen:
            continue
        seen.add(pk)
        out.append({
            "system": system,
            "fact_pk": pk,
            "fact_name": fp.get("fact_name", ""),
            "fact_kind": fp.get("fact_kind", ""),
            "category": fp.get("category", ""),
            "angle": fp.get("angle", ""),
            "hook": fp.get("hook", ""),
            "body": fp.get("body", ""),
            "cta": fp.get("cta", ""),
            "day": it.get("day", fp.get("day", "")),
            "youtube_url": it.get("youtube_url", ""),
        })
    return out


def all_facts():
    result = {}
    for system in SYSTEMS:
        try:
            result[system] = facts_for(system)
        except Exception as ex:
            print(f"  [registry] skip {system}: {ex}")
            result[system] = []
    return result
