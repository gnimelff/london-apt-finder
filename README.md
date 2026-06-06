# London Apartment Finder

An automated apartment hunting agent that monitors Rightmove, OpenRent, and OnTheMarket, enriches each listing with real commute data and local stats, scores it against your preferences using Claude AI, and sends a Telegram notification for anything worth seeing.

Runs on GitHub Actions once daily. Total cost: ~$1–2/month.

## How It Works

```
Scrapers (Rightmove · OpenRent · OnTheMarket)
          │
          ▼
Deduplication (SQLite — persisted via GitHub Actions cache)
          │
          ▼
Enrichment Pipeline
  ├─ TfL Journey Planner API  →  door-to-door tube/rail commute time
  ├─ Cycling route estimate   →  bike commute time + distance
  ├─ EPC Register API         →  energy efficiency rating
  ├─ postcodes.io             →  borough + lat/lng fallback
  └─ Text analysis            →  floor level + basement detection
          │
          ▼
Claude Haiku scoring (1–10, with rationale + deal flags)
scored against your preferences.yaml
          │
          ▼
Telegram notification (listings at or above your score threshold)
```

## Features

- **3 site scrapers** — Rightmove, OpenRent, OnTheMarket with dedup across all three
- **Real commute data** — TfL Journey Planner for tube/rail; cycling time and distance estimate
- **EPC ratings** — energy efficiency pulled from the national register
- **Basement detection** — text analysis flags lower-ground and basement flats automatically
- **AI scoring** — Claude Haiku scores each listing 1–10 with a rationale, area vibe summary, and deal flags
- **YAML preferences** — edit `preferences.yaml` to change your budget, commute limit, or deal-breakers; changes take effect on the next run with no redeploy
- **Zero-cost database** — SQLite file persisted between GitHub Actions runs via the Actions cache
- **Telegram notifications** — batched HTML-formatted messages with score, price, commute, and a direct link

## Tech Stack

| Layer | Technology |
|---|---|
| Scrapers | Python · httpx · BeautifulSoup |
| Enrichment | TfL API · postcodes.io · EPC Register |
| Scoring | Claude Haiku (Anthropic) |
| Notifications | Telegram Bot API |
| Database | SQLite (GitHub Actions cache) |
| Automation | GitHub Actions cron |

## Setup

### 1. Get API keys

| Service | Where | Notes |
|---|---|---|
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | Claude Haiku, ~$1–2/month |
| TfL | [api-portal.tfl.gov.uk](https://api-portal.tfl.gov.uk) | Free, 500 req/day |
| EPC Register | [epc.opendatacommunities.org](https://epc.opendatacommunities.org) | Free — base64 encode `email:key` after registering |
| Telegram | @BotFather on Telegram | Free — `/newbot` to create a bot, then fetch `/getUpdates` to get your chat ID |

### 2. Configure your search

Edit `preferences.yaml`:

```yaml
commute_destination:
  address: "Your office address"
  lat: 51.5074
  lng: -0.1278

must_haves:
  max_commute_mins: 40
  max_price_pcm: 3000
  min_bedrooms: 1

deal_breakers:
  - commute > 40 minutes
  - price > £3,000/month
  - basement flat
```

The scorer re-reads this file on every run — no redeploy needed.

### 3. Deploy to GitHub Actions

1. Fork this repo (keep it private — your preferences contain your commute destination)
2. Go to **Settings → Secrets and variables → Actions** and add each key from `.env.example`
3. The workflow runs daily at 10am BST; trigger a test run from **Actions → Scrape London Apartments → Run workflow**

### 4. Test locally first

```bash
cp .env.example .env
# fill in your keys
pip install -r requirements.txt
python run.py
```

## Scoring Logic

Claude Haiku scores each listing on a transparent rubric:

| Factor | Adjustment |
|---|---|
| Base | 7 |
| Commute ≤ 20 min | 0 |
| Commute 21–30 min | −1 |
| Commute 31–40 min | −2 |
| Commute > 40 min | deal-breaker (≤ 3) |
| Price ≤ £2,500/mo | 0 |
| Price £2,501–£2,750 | −1 |
| Price £2,751–£3,000 | −2 |
| Price > £3,000 | deal-breaker (≤ 3) |
| Cycling < 20 min | +2 |
| Cycling 20–30 min | +1 |
| Unfurnished | −1 |
| Basement flat | deal-breaker (≤ 3) |
| New build / recently renovated | +1 |

Adjust the scoring prompt in `scoring/claude.py` to match your own priorities.

## Cost

| Item | Cost |
|---|---|
| GitHub Actions | Free |
| TfL API | Free |
| EPC Register | Free |
| postcodes.io | Free |
| Telegram Bot | Free |
| Claude Haiku | ~$0.50–2/month |
| **Total** | **~$1–2/month** |
