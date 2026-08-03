# CLAUDE.md

## Project Overview
"It's Already Written." — TTRPG rules/facts/news blog, sister project to Bizzal Games YT, live at https://bizzal70.github.io/itsalreadywritten/. Jekyll + GitHub Pages, three content tiers, all Claude-generated and auto-tweeted to @ItsAlrdyWritten. **This is live and actively publishing, not scaffolding** — 37 real posts since 2026-07-05 across all three tiers, last 15 Actions runs all successful through today.

- **Weekly Issue** (Friday) — `issues.py`. **Note:** its own docstring claims output goes to `_drafts/` for human review and is "NOT auto-published, NOT tweeted" — this is stale/wrong. The actual code writes to `_posts/` (comment: "auto-published (audit after a few)") and commit history confirms it auto-publishes and auto-tweets identically to the other two tiers. Trust the code and commit history over the docstring.
- **Daily Field Note** — `field_note.py`. Picks either a curated cross-system "rules atom" or a fresh high-signal news item.
- **Weekly RTFM** (Wednesday) — `rtfm.py`. Long-form, evergreen, grounded only in curated system sources — deliberately not news-driven.

**Notable dependency**: `registries.py` pulls its "rules atom" facts by HTTP GET directly from `Bizzal-Games-YT-PUB`'s published registry JSON (`raw.githubusercontent.com/.../data/state/published_registry_{system}.json`). This repo does not maintain its own facts corpus — it reuses the sister YouTube pipeline's already-published fact registries. The two projects are linked in production, not just conceptually.

## Tech Stack
- Jekyll + GitHub Pages (`Gemfile`: github-pages, jekyll-feed/seo-tag/sitemap)
- Claude API (`anthropic` SDK), model constant `"claude-opus-4-8"` across all three generators
- `feedparser` (RSS) + Mastodon (dice.camp tag feeds) — `feeds.py`, no keys required
- SQLite `articles.db` — **not committed**, rebuilt by re-scraping every run (unlike the sister blogs); only the `scraper/state/*.json` registries persist dedup across runs
- `tweepy` (OAuth 1.0a) — tweets on every new post via `tweet_on_publish.py`, which polls the live Pages URL until it 200s before tweeting so a tweet never links to a 404
- Pillow — thumbnail cards, shared style module across this blog + itsalreadywhen + itsalreadypriced

## Commands
No local dev loop — cloud-only, no persistent local clone.
```bash
gh workflow run daily-field-note.yml
gh workflow run weekly-issue.yml
gh workflow run weekly-rtfm.yml
gh workflow run deploy.yml
gh workflow run tweet-on-publish.yml -f tweet_latest=true   # manual test: tweet newest post
```

## Code Style
- No em dashes, no AI-authorship disclosure — enforced in **code** (`style.py`'s `normalize()` strips dashes/curly quotes unconditionally, `lint()` flags banned AI-tell phrases and forces a stricter retry), not just requested in the prompt, "so a tell can't reach the site even if the model backslides."
- Citations must never be LLM-invented: `sources.py` hardcodes canonical per-system landing pages (SRD, Arcane Library, Goodman Games) rather than deep-linking (explicit "high dead-link risk" comment); `resources.py`/`validate_sources()` drops any model-declared source URL that isn't a member of the actual scraped input set.

## Testing
- No test suite — validate via `workflow_dispatch` and read the actual published post.
- Field Note quality is gated by a deterministic substance-floor checker (`note_quality.py`) for the same documented reason as the sister blogs: an LLM judge over-flagged elsewhere in this project family, so this is regex/word-count based on purpose.
- `DRY_RUN=1` is an explicit opt-out env var on the generators — production workflow runs don't set it, so a real run always writes/commits for real.

## Repository Etiquette
- `README.md` is comprehensive and was corroborated line-by-line against the actual workflows/scripts during this review — treat it as accurate, with one known exception (the `issues.py` docstring, see Boundaries).
- Content licensing split: code MIT, published post content CC BY-NC 4.0 (`LICENSE-CONTENT.md`).

## Architecture Notes
- `feeds.py` — RSS + Mastodon source registry, `SYSTEM_KEYWORDS`/`focus_match()` weight content toward dnd5e/shadowdark/dcc
- `scraper.py` — scores articles by recency + source authority + engagement + system-focus; dedupes by URL; rebuilds `articles.db` fresh each run
- `registries.py` — fetches rules-atom facts from the sibling `Bizzal-Games-YT-PUB` repo's published registries (see Overview) — this is the real cross-repo link, not just conceptual similarity
- `note_quality.py` — deterministic Field Note substance floor
- `style.py` — code-enforced AI-tell guard (dash/quote normalization + banned-phrase lint)
- `sources.py` / `resources.py` — deterministic citation building + keyword-overlap "Related" section (recency-only ranking was a past design mistake, since fixed — see Boundaries)
- `x_thumbnail.py` — shared Pillow thumbnail generator across all three "It's Already *" blogs
- `scraper/state/published_fieldnotes.json` / `published_issues.json` / `published_rtfm.json` — committed dedup registries (mix of numeric and string `fact_pk` values in the fieldnotes one)
- `scraper/issue_number.txt` — plain incrementing counter (currently `5`, matches 5 published issues) — **unlike Bizzal-Games-YT-PUB's equivalent counter, which was replaced after desyncing; this repo's file-based counter is currently consistent with reality but carries the same class of risk if a commit-back step ever silently fails**

## Boundaries — What NOT To Do
- **Cloud-only, no exceptions** — no persistent local clone of this repo exists or should exist.
- **`issues.py`'s docstring is wrong — don't trust it.** It claims weekly Issues save to `_drafts/` and are not auto-published/tweeted. The real, current behavior (confirmed by code and commit history) is auto-publish to `_posts/` and auto-tweet, same as the other two tiers. If you need the drafts-for-review behavior the docstring describes, it doesn't exist yet and would need to be built — don't assume it's already there.
- **RTFM must never be sourced from the article database or current news** — explicitly evergreen/framework-grounded by design.
- **Never let the LLM invent a citation URL** — always route through `sources.py` (hardcoded canonical pages) or `resources.py`'s `validate_sources()` (filters against the real scraped-URL set).
- **Blocked/paid scrape sources are deliberately off, not missing**: `feeds.py` documents Reddit/Kickstarter/Bluesky as blocked (403 from CI/datacenter IPs) with `BRIGHTDATA_ENABLED = False` pending a future Bright Data integration — don't "fix" this by re-enabling them without that adapter in place.
- **CP1252 mojibake encoding bug hit both source and already-published content on 2026-07-31** (4 same-day fix commits, across generator source and live posts) — if you see garbled characters in generated text, check encoding handling before assuming it's a content problem.
- **`deploy.yml` deliberately ignores `scraper/**` path changes** (`paths-ignore`) so DB/state-only commits don't trigger a site rebuild — don't remove this without understanding why it's there.

## Workflow Preferences
- One fix at a time; this pipeline auto-commits and auto-tweets on every scheduled run, so a bad generator change ships fast and publicly.
- Validate content-generation changes via manual `workflow_dispatch` and read the actual post file before trusting it.

## Environment / Secrets
- `GH_PAT` — used for checkout in the three content-generating workflows so the resulting push (not the default `GITHUB_TOKEN`) fans out to `deploy.yml` and `tweet-on-publish.yml`
- `ANTHROPIC_API_KEY` — Claude API calls for all three generators
- `X_API_KEY` / `X_API_SECRET` — X OAuth 1.0a consumer key/secret
- `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` — X OAuth 1.0a user access token/secret
