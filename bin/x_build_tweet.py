#!/usr/bin/env python3
"""Build tweet text from a Jekyll post frontmatter and write to GITHUB_OUTPUT."""
import argparse
import os
import re
from pathlib import Path

import yaml


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--post", required=True)
    p.add_argument("--url", required=True)
    args = p.parse_args()

    text = Path(args.post).read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    fm = yaml.safe_load(m.group(1)) if m else {}

    issue = fm.get("issue", "?")
    summary = str(fm.get("summary", "")).strip()

    tweet = f"Issue #{issue} is live.\n\n{summary}\n\n↗ {args.url}"
    if len(tweet) > 278:
        tweet = tweet[:275] + "…"

    gh_output = os.environ.get("GITHUB_OUTPUT", "")
    if gh_output:
        with open(gh_output, "a", encoding="utf-8") as f:
            f.write("text<<TWEET_EOF\n")
            f.write(tweet + "\n")
            f.write("TWEET_EOF\n")

    print(f"[x_build_tweet] {len(tweet)} chars")
    print(tweet)


if __name__ == "__main__":
    main()
