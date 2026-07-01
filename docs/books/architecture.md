# SMMA SaaS v2 - System Architecture

## Complete File Architecture

```
Discord Layer
  bot.py        - compatibility entry point
  views.py      - persistent Discord buttons and embed views

AI + Intelligence Layer
  ai_agent.py   - compatibility AI facade
  learner.py    - tracks outcomes and pricing history
  report_gen.py - weak-point analysis reports

Scraping + Audit Layer
  scraper.py        - business and influencer scan facade
  social_checker.py - social profile audit compatibility facade
  post_analyzer.py  - view count and engagement scoring

Outreach Layer
  email_sender.py - Gmail SMTP facade
  dm_sender.py    - platform-ready DM drafts
  followup.py     - interest tracking and follow-up scheduling

Data + Storage Layer
  airtable_client.py - Airtable operations facade
  order_manager.py   - deals, builds, Order IDs facade
  post_builder.py    - text and image-prompt post packages

Config + Runtime
  config.py
  railway.json
  Procfile
  nixpacks.toml
```

## Discord Commands

| Command | Purpose |
|---------|---------|
| `/scan` | v2 weak-lead scan with dropdowns |
| `/scrape` | backward-compatible scan command |
| `/dc` | close deal and generate Order ID |
| `/build` | build text + image-prompt post package |
| `/followup` | track interest and schedule follow-up |
| `/status` | pipeline stats dashboard |

## Airtable Tables

Raw Dump, Deals, Post Builds, Email Log, Reports, Follow-ups, Learner Data,
and Pricing History.
