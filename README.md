# It's Already Written.

*The rules are already written.*

A fully automated, self-publishing TTRPG publication. It scrapes, writes, publishes, and posts to X — no manual steps required.

**Live site:** https://bizzal70.github.io/itsalreadywritten  
**X:** [@ItsAlrdyWritten](https://x.com/ItsAlrdyWritten)

Sister site to [It's Already When.](https://github.com/bizzal70/itsalreadywhen) (cyber) and [It's Already Priced.](https://github.com/bizzal70/itsalreadypriced) (crypto).

---

## Three sections, three cadences

| Section | Cadence | What it is |
|---|---|---|
| **Issues** | Weekly, Friday 10am MT | Long-form digest: releases, rules discourse, industry news, the week's verdict |
| **Field Notes** | Daily, 7am MT | Short tactical entries on the most relevant TTRPG item from the last 24 hours |
| **RTFM** | Weekly, Wednesday 9am MT | Evergreen rules deep dives grounded in official system documentation — not news-driven |

Each section has its own index page and RSS feed.

---

## How it works

```
7:00 AM MT daily          7:00 AM MT daily         Friday 10 AM MT          Wednesday 9 AM MT
─────────────────         ─────────────────         ───────────────          ─────────────────
RSS feeds (TTRPG)         Last 24h articles          Week's articles          Next unused topic
      │                         │                         │                         │
      ▼                         ▼                         ▼                         ▼
  scraper.py              field_note.py              issues.py                  rtfm.py
      │                         │                         │                         │
      ▼                         ▼                         ▼                         ▼
 articles.db              _posts/ field note          _posts/ issue            _posts/ rtfm
                                │                         │                         │
                                └─────────────────────────┴─────────────────────────┘
                                                          │
                                                          ▼
                                              deploy.yml → GitHub Pages
                                                          │
                                                          ▼
                                          X card thumbnail generated (Pillow)
                                                          │
                                                          ▼
                                                  Tweet posted to X
```

Everything runs on GitHub Actions. No local machine, server, or cron required.

---

## Workflows

| Workflow | Schedule | What it does |
|---|---|---|
| `daily-field-note.yml` | 7am MT daily | Scrapes feeds; generates Field Note if anything is high-signal; pushes; tweets with card |
| `weekly-issue.yml` | Friday 10am MT | Catches up missed articles; generates Issue with Claude; pushes; tweets with card |
| `weekly-rtfm.yml` | Wednesday 9am MT | Picks next unused RTFM topic; generates article; pushes; tweets |
| `tweet-on-publish.yml` | On push to `_posts/` | Waits for page to go live (200 OK), then posts tweet with generated thumbnail card |
| `deploy.yml` | On every push to `main` | Builds + deploys Jekyll site to GitHub Pages |

All scheduled workflows support `workflow_dispatch` for manual runs.

---

## Scraper components

| File | Purpose |
|---|---|
| `scraper/feeds.py` | TTRPG RSS sources (EN World, RPGSite, RPGBOT, Dicebreaker, and others) |
| `scraper/scraper.py` | Pulls feeds, deduplicates by URL hash, caches to `articles.db` |
| `scraper/issues.py` | Generates weekly Issue from this week's unused articles via Claude API |
| `scraper/field_note.py` | Generates daily Field Note from last 24h articles; skips if nothing high-signal |
| `scraper/rtfm.py` | Picks next unused topic from topic backlog; generates evergreen RTFM article |
| `scraper/sources.py` | Curated, stable per-system source URLs (D&D 5e SRD, Shadowdark, DCC) — never deep-links or LLM-generated URLs |
| `scraper/resources.py` | Builds deterministic source citations for rules references |
| `scraper/registries.py` | Tracks published issues and field notes to prevent duplicates |
| `scraper/style.py` | Per-system tone and voice rules for Claude prompts |
| `scraper/x_thumbnail.py` | Generates 1200×675 X card image (Pillow): warm dark background, amber accent, blog name + issue number + summary |
| `scraper/tweet_on_publish.py` | Posts tweet with thumbnail when a new post is detected; waits for page to go live first |

---

## Content rules

- **No em dashes** — a deliberate choice to avoid an obvious AI-writing tell
- **No AI disclosure** in post copy
- **RTFM is not news-driven** — grounded only in official system documentation, not the scraped article DB
- **Source links are deterministic** — `sources.py` uses curated, stable landing pages (SRD pages, publisher sites); never hallucinated deep links
- **Per-system tone** — `style.py` controls voice per RPG system (D&D 5e, Shadowdark, DCC)
- **Duplicate prevention** — `registries.py` tracks published items so re-runs never double-post

---

## Required secrets

Settings → Secrets and variables → Actions:

| Secret | Purpose |
|---|---|
| `GH_PAT` | Personal access token with repo write access (used for committing posts) |
| `ANTHROPIC_API_KEY` | Claude API for content generation |
| `X_API_KEY` / `X_API_SECRET` | X app consumer keys (OAuth 1.0a) |
| `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | X user access tokens |

---

## Site structure

```
_posts/           Issues + Field Notes + RTFM articles (all in one collection)
_layouts/         Jekyll templates (post, default)
assets/           CSS, fonts, images
scraper/          All automation scripts
  state/          Published item registries (committed, version-controlled)
.github/workflows/ GitHub Actions workflows
```

Issue numbers tracked in `scraper/issue_number.txt`, incremented on each Issue run.
