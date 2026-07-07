"""
News/social ingestion for It's Already Written.

Pulls broad TTRPG news (RSS) + discussion (Reddit) + crowdfunding (Kickstarter)
into a local SQLite store shared by all three tiers. Each row is tagged with the
user-systems it mentions and given a signal score (recency + source authority +
engagement + system-focus boost). Dead sources are skipped, never fatal.

Run: python scraper.py     (no keys required)
"""

import re
import json
import time
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from calendar import timegm

import feedparser

from feeds import (RSS_FEEDS, MASTODON_INSTANCE, MASTODON_TAGS,
                   SOURCE_WEIGHT, focus_match)

DB_PATH = Path(__file__).parent / "articles.db"
UA = "iaw-scraper/1.0 (+https://bizzal70.github.io/itsalreadywritten)"


def init_db(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            url            TEXT PRIMARY KEY,
            source         TEXT,
            platform       TEXT,          -- rss | reddit | kickstarter | brightdata
            title          TEXT,
            summary        TEXT,
            published_at   TEXT,          -- ISO8601 UTC
            system_tags    TEXT,          -- csv of dnd5e/shadowdark/dcc, may be ''
            engagement     INTEGER DEFAULT 0,
            score          REAL DEFAULT 0,
            used_in_fieldnote INTEGER DEFAULT 0,
            used_in_rtfm      INTEGER DEFAULT 0,
            used_in_issue     INTEGER DEFAULT 0,
            fetched_at     TEXT
        )
    """)
    conn.commit()


def _clean(html):
    return re.sub(r"<[^>]+>", "", html or "").strip()


def _iso(struct_time):
    if not struct_time:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(timegm(struct_time), tz=timezone.utc).isoformat()


def _score(source, published_at, engagement, systems):
    """Higher = more worth publishing. Recency-decayed, authority- and focus-weighted."""
    try:
        age_h = (datetime.now(timezone.utc)
                 - datetime.fromisoformat(published_at)).total_seconds() / 3600
    except Exception:
        age_h = 72
    recency = max(0.0, 1.0 - age_h / 168.0)          # linear decay over 7 days
    authority = SOURCE_WEIGHT.get(source, 0.5)
    eng = min(1.0, (engagement or 0) / 500.0)         # reddit ups etc.
    focus = 1.0 if systems else 0.0                   # weight the user's systems
    return round(2.0 * focus + 1.2 * recency + 0.8 * authority + 0.6 * eng, 4)


def _upsert(conn, row, system_hint=None):
    matched = set(focus_match(f"{row['title']} {row['summary']}"))
    if system_hint:            # e.g. a dice.camp #shadowdark feed => shadowdark
        matched.add(system_hint)
    systems = ",".join(sorted(matched))
    row["system_tags"] = systems
    row["score"] = _score(row["source"], row["published_at"], row["engagement"], systems)
    row["fetched_at"] = datetime.now(timezone.utc).isoformat()
    # keep usage flags if the row already exists; only refresh content/score
    conn.execute("""
        INSERT INTO articles (url, source, platform, title, summary, published_at,
                              system_tags, engagement, score, fetched_at)
        VALUES (:url,:source,:platform,:title,:summary,:published_at,
                :system_tags,:engagement,:score,:fetched_at)
        ON CONFLICT(url) DO UPDATE SET
            summary=excluded.summary, score=excluded.score,
            engagement=excluded.engagement, system_tags=excluded.system_tags
    """, row)


def fetch_rss(conn):
    n = 0
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, agent=UA)
            for e in feed.entries[:25]:
                link = e.get("link")
                if not link:
                    continue
                _upsert(conn, {
                    "url": link, "source": source, "platform": "rss",
                    "title": _clean(e.get("title", ""))[:300],
                    "summary": _clean(e.get("summary", ""))[:800],
                    "published_at": _iso(e.get("published_parsed") or e.get("updated_parsed")),
                    "engagement": 0,
                })
                n += 1
        except Exception as ex:
            print(f"  [rss] skip {source}: {ex}")
    conn.commit()
    print(f"  rss: {n} entries")


def fetch_mastodon(conn):
    """dice.camp (TTRPG Mastodon) public tag RSS. Toots have no title, so we
    synthesize one from the author + text; the feed's tag seeds the system."""
    n = 0
    for tag, system in MASTODON_TAGS:
        url = f"{MASTODON_INSTANCE}/tags/{tag}.rss"
        try:
            feed = feedparser.parse(url, agent=UA)
            for e in feed.entries[:20]:
                link = e.get("link")
                if not link:
                    continue
                text = _clean(e.get("summary", "") or e.get("title", ""))
                author = (e.get("author", "") or "").lstrip("@")
                _upsert(conn, {
                    "url": link, "source": f"dice.camp #{tag}", "platform": "mastodon",
                    "title": (f"@{author}: " if author else "") + text[:120],
                    "summary": text[:800],
                    "published_at": _iso(e.get("published_parsed") or e.get("updated_parsed")),
                    "engagement": 0,
                }, system_hint=system)
                n += 1
        except Exception as ex:
            print(f"  [mastodon] skip #{tag}: {ex}")
    conn.commit()
    print(f"  mastodon: {n} entries")


def prune(conn, days=30):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    conn.execute("DELETE FROM articles WHERE published_at < ? AND used_in_issue = 0", (cutoff,))
    conn.commit()


def main():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    print("Scraping TTRPG news/social...")
    fetch_rss(conn)
    fetch_mastodon(conn)
    prune(conn)
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    tagged = conn.execute("SELECT COUNT(*) FROM articles WHERE system_tags != ''").fetchone()[0]
    print(f"Store: {total} articles ({tagged} match a focus system).")
    conn.close()


if __name__ == "__main__":
    main()
