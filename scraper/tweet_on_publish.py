"""
Tweet-on-publish for It's Already Written (@ItsAlrdyWritten).
Triggered by .github/workflows/tweet-on-publish.yml when a new post is added
under _posts/. Waits for the live GitHub Pages URL to return 200, then posts to X
with a generated 1200x675 thumbnail card.

Env:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET  (repo secrets)
  POST_PATHS    space/newline-separated repo-relative paths of newly added posts
  TWEET_LATEST  'true' to tweet the newest post (manual workflow_dispatch test)
"""

import os
import re
import glob
import time
import urllib.request
from pathlib import Path

BLOG_URL = "https://bizzal70.github.io/itsalreadywritten"
HANDLE = "ItsAlrdyWritten"
ROOT = Path(__file__).resolve().parent.parent


def parse_front_matter(text):
    """Parse ONLY top-level scalar keys (column 0)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
            if mm:
                k, v = mm.group(1), mm.group(2).strip()
                if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
                    v = v[1:-1]
                fm[k] = v
    return fm


def resolve(path):
    p = Path(path)
    if p.parent.name != "_posts" or p.suffix != ".md":
        return None
    full = ROOT / path
    if not full.exists():
        return None
    fm = parse_front_matter(full.read_text(encoding="utf-8"))
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})-(.+)$", p.stem)
    if not m:
        return None
    y, mo, d, slug = m.groups()
    url = f"{BLOG_URL}/{y}/{mo}/{d}/{slug}/"
    return {"fm": fm, "url": url}


def wait_for_200(url, timeout=300, interval=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "iaw-tweet-bot"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def build_tweet(fm, url):
    title = fm.get("title", "")
    summary = fm.get("summary", "")
    tier = (fm.get("tier", "") or "").lower()
    system = (fm.get("system", "") or "").lower()
    issue = fm.get("issue", "")

    sys_tag = {
        "dnd5e": "#DnD",
        "shadowdark": "#Shadowdark",
        "dcc": "#DCCRPG",
    }.get(system, "")

    if tier == "issues" or issue.isdigit():
        head = f"It's Already Written. — Issue #{int(issue):03d}" if issue.isdigit() \
               else "It's Already Written. — Issues"
        body, tags = (summary or title), "#TTRPG #TabletopRPG #RPG"
    elif tier == "rtfm":
        head, body = "It's Already Written. — RTFM", (summary or title)
        tags = " ".join(t for t in ("#TTRPG", sys_tag, "#RPG") if t)
    else:
        head, body = "It's Already Written. — Field Note", title
        tags = " ".join(t for t in ("#TTRPG", sys_tag) if t)

    def assemble(b):
        return f"{head}\n\n{b}\n\n{url}\n\n{tags}"

    tweet = assemble(body)
    if len(tweet) > 280:
        overhead = len(assemble("")) + 3
        body = body[: max(0, 280 - overhead)].rstrip() + "..."
        tweet = assemble(body)
    return tweet


def make_thumbnail(fm):
    try:
        from x_thumbnail import render
        return render("written", fm)
    except Exception as e:
        print(f"[x_thumbnail] WARNING: {e}; posting without image")
        return None


def main():
    creds = {k: os.environ.get(k) for k in
             ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")}
    missing = [k for k, v in creds.items() if not v]
    if missing:
        print(f"X secrets not configured ({', '.join(missing)}). Skipping tweet.")
        return

    targets = []
    raw = os.environ.get("POST_PATHS", "").strip()
    if raw:
        targets = [t for t in re.split(r"\s+", raw) if t]
    elif os.environ.get("TWEET_LATEST", "").lower() == "true":
        posts = sorted(glob.glob(str(ROOT / "_posts" / "*.md")), reverse=True)
        if posts:
            targets = [str(Path(posts[0]).relative_to(ROOT)).replace("\\", "/")]

    if not targets:
        print("No newly added posts to tweet.")
        return

    import tweepy

    client = tweepy.Client(
        consumer_key=creds["X_API_KEY"],
        consumer_secret=creds["X_API_SECRET"],
        access_token=creds["X_ACCESS_TOKEN"],
        access_token_secret=creds["X_ACCESS_TOKEN_SECRET"],
    )
    try:
        me = client.get_me()
        print(f"READ-AUTH OK: authenticated as @{me.data.username}")
    except Exception as e:
        print(f"READ-AUTH FAILED: {type(e).__name__}: {e}")

    auth = tweepy.OAuth1UserHandler(
        creds["X_API_KEY"], creds["X_API_SECRET"],
        creds["X_ACCESS_TOKEN"], creds["X_ACCESS_TOKEN_SECRET"],
    )
    v1 = tweepy.API(auth)

    for path in targets:
        info = resolve(path)
        if not info:
            print(f"Skip (not a publishable _posts/*.md): {path}")
            continue
        print(f"Waiting for live URL: {info['url']}")
        if not wait_for_200(info["url"]):
            print(f"  URL never returned 200 within timeout; skipping {path}")
            continue

        thumb_path = make_thumbnail(info["fm"])
        media_ids = None
        if thumb_path:
            try:
                media = v1.media_upload(thumb_path)
                media_ids = [media.media_id]
                print(f"[x_thumbnail] media_id={media.media_id}")
            except Exception as e:
                print(f"[x_post] WARNING: media upload failed ({e}); posting without image")

        tweet = build_tweet(info["fm"], info["url"])
        print(f"Posting:\n{tweet}\n")
        kwargs = {"text": tweet}
        if media_ids:
            kwargs["media_ids"] = media_ids
        resp = client.create_tweet(**kwargs)
        print(f"Tweeted: https://x.com/{HANDLE}/status/{resp.data['id']}")

        if thumb_path:
            try:
                os.unlink(thumb_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
