#!/usr/bin/env python3
"""Upload image and post tweet to X/Twitter via API v2 + v1.1 media upload."""
import argparse
import os
import sys
import tweepy


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True, help="Path to PNG/JPG thumbnail")
    p.add_argument("--text", required=True, help="Tweet text (<=280 chars)")
    args = p.parse_args()

    for var in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"):
        if not os.environ.get(var):
            print(f"[x_post] ERROR: {var} is not set", file=sys.stderr)
            sys.exit(1)

    # v1.1 auth required for media upload
    auth = tweepy.OAuth1UserHandler(
        os.environ["X_API_KEY"],
        os.environ["X_API_SECRET"],
        os.environ["X_ACCESS_TOKEN"],
        os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    v1 = tweepy.API(auth)
    media = v1.media_upload(args.image)
    print(f"[x_post] uploaded media_id={media.media_id}")

    # v2 client for tweet creation
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    resp = client.create_tweet(text=args.text, media_ids=[media.media_id])
    print(f"[x_post] posted tweet id={resp.data['id']}")


if __name__ == "__main__":
    main()
