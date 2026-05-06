# London Apartment Finder

Monitors Rightmove, OpenRent, and OnTheMarket every 30 minutes. Enriches each new listing with TfL commute time, crime data, and EPC rating. Scores it against your preferences using Claude Haiku. Sends a WhatsApp message for anything scoring 7+.

Runs entirely on free infrastructure via GitHub Actions + Supabase.

## One-time setup

No database to create — the app uses a local SQLite file (`seen.db`) that's persisted between GitHub Actions runs via the Actions cache. Zero external DB services needed.

### 1. Get API keys

| Service | URL | Notes |
|---|---|---|
| Anthropic | [console.anthropic.com](https://console.anthropic.com) | Claude Haiku, ~$2/month |
| TfL | [api-portal.tfl.gov.uk](https://api-portal.tfl.gov.uk) | Free, 500 req/day |
| EPC Register | [epc.opendatacommunities.org](https://epc.opendatacommunities.org) | Free, register + base64 encode `email:key` |
| CallMeBot | See below | Free WhatsApp notifications |

**CallMeBot setup:**
1. Save `+34 644 59 78 78` in your contacts as "CallMeBot"
2. Send it this WhatsApp message: `I allow callmebot to send me messages`
3. You'll receive your API key within 60 seconds

### 3. Configure preferences
Edit `preferences.yaml` to set your budget, commute threshold, and preferred neighbourhoods.

### 3. Deploy to GitHub Actions
1. Push this repo to a private GitHub repo
2. Go to Settings → Secrets and variables → Actions → add each key from `.env.example`
3. The workflow runs every 30 minutes automatically; `seen.db` is cached between runs
4. Trigger a manual run from Actions → "Scrape London Apartments" → Run workflow to test

### 4. Test locally first
```bash
cp .env.example .env
# fill in .env
pip install -r requirements.txt
python run.py
```

## Adjusting your preferences
Edit `preferences.yaml` — the scorer re-reads it on every run, so changes take effect immediately with no redeploy needed.

## Adding Zoopla
Zoopla uses an internal GraphQL API that's harder to maintain. The simplest approach is to add an [Apify actor](https://apify.com/automation-lab/rightmove-scraper) and call it via their API. ~$5-10/month.

## Cost
| Item | Cost |
|---|---|
| SQLite (local file, no DB service) | Free |
| GitHub Actions | Free |
| TfL API | Free |
| EPC + crime APIs | Free |
| Claude Haiku | ~$0.50–2/month |
| CallMeBot | Free |
| **Total** | **~$1–2/month** |
