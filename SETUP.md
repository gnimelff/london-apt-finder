# Step-by-step setup guide

Total time: ~30 minutes. All services are free except the Anthropic API (~$1–2/month).

---

## Prerequisites

- Python 3.11 or 3.12 installed (`python3 --version`)
- A GitHub account
- A WhatsApp account on your phone

---

## Step 1 — Get the code onto your machine

```bash
# Either clone if you've pushed it to GitHub already, or just work from the folder:
cd ~/VibeCoding/other/london-apt-finder

# Install Python dependencies
pip3 install -r requirements.txt
```

---

## Step 2 — Get your API keys (do all of these, takes ~15 min)

### 2a. Anthropic (Claude Haiku scorer)
1. Go to **https://console.anthropic.com/**
2. Sign up / sign in
3. Click **API Keys** in the left sidebar → **Create key**
4. Copy the key (starts with `sk-ant-...`)

### 2b. TfL (commute time)
1. Go to **https://api-portal.tfl.gov.uk/**
2. Click **Sign up** (top right) → fill in the form
3. Check your email and click the confirmation link
4. Sign in → click **Products** in the nav → click **500 Requests per min**
5. Give the subscription a name (anything) → click **Subscribe**
6. Go to **Profile** (top right) → scroll down to **Primary key** → copy it

### 2c. EPC Register (energy ratings)
1. Go to **https://epc.opendatacommunities.org/**
2. Click **Register** → fill in the form (name, email, organisation = "Personal")
3. Check your email and confirm
4. Sign in → go to **My Account** → copy your **API key**
5. Now base64-encode `your@email.com:your_api_key` by running this in your terminal:
   ```bash
   echo -n "your@email.com:your_api_key" | base64
   ```
6. Copy the output — that's your `EPC_API_KEY`

### 2d. CallMeBot (WhatsApp notifications)
1. On your phone, save the number **+34 644 59 78 78** as a contact named "CallMeBot"
2. Open WhatsApp → send that contact this exact message:
   ```
   I allow callmebot to send me messages
   ```
3. Within 60 seconds you'll receive a reply with your API key. Copy it.
4. Your `WHATSAPP_PHONE` is your number in international format with no `+` or spaces
   - Example: UK number `07911 123456` → `447911123456`

---

## Step 3 — Test locally first

Create your `.env` file:

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
ANTHROPIC_API_KEY=sk-ant-...
TFL_API_KEY=abc123...
EPC_API_KEY=eW91ckBlbWFpbC5jb206eW91cmtleQ==
CALLMEBOT_API_KEY=123456
WHATSAPP_PHONE=447911123456
SCORE_THRESHOLD=7
```

Run the pipeline:

```bash
python3 run.py
```

**What to expect on first run:**
- It scrapes ~75–150 listings across OpenRent, Rightmove, OnTheMarket
- Each new listing gets enriched (TfL, crime, EPC) — takes ~2–5 seconds per listing
- Claude scores it — near-instant
- Listings scoring 7+ send a WhatsApp message to you
- All seen listing IDs are saved to `seen.db`

Run it a second time — it should say "Nothing new. Done." because everything is already in `seen.db`.

**If something errors:**
- `DATABASE_URL` error → you don't need one, SQLite is automatic — check `config.py` isn't importing it
- `TFL_API_KEY` 401 → double-check you subscribed to the 500 req/min product on the TfL portal
- `EPC_API_KEY` 401 → make sure you base64-encoded `email:key` (with a colon, no spaces)
- `CALLMEBOT` no message → re-send the opt-in WhatsApp message and wait a minute

---

## Step 4 — Edit your preferences

Open **`preferences.yaml`** and adjust to your taste. The key fields:

```yaml
must_haves:
  max_commute_mins: 35      # door-to-door to Waterloo
  max_price_pcm: 3000
  min_bedrooms: 1

budget:
  target_pcm: 2500          # scorer rewards flats under this
  max_pcm: 3000

deal_breakers:
  - studio (0 bedrooms)
  - commute > 50 mins
  - price > 3000

neighborhoods_preferred:
  - Brixton, Clapham, Stockwell, Oval, Kennington
  - Bermondsey, Borough, Elephant & Castle, Peckham
  - Camberwell, Herne Hill
```

Changes take effect on the **next run** — no redeploy needed.

---

## Step 5 — Push to GitHub and set up the cron

### 5a. Create a private GitHub repo
1. Go to **https://github.com/new**
2. Name it `london-apt-finder`
3. Set it to **Private**
4. Do NOT initialise with README (you already have files)
5. Click **Create repository**

### 5b. Push your code
```bash
cd ~/VibeCoding/other/london-apt-finder
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/london-apt-finder.git
git push -u origin main
```

### 5c. Add your secrets to GitHub
1. On your repo page → **Settings** (top tab) → **Secrets and variables** → **Actions**
2. Click **New repository secret** for each of the following:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `TFL_API_KEY` | your TfL primary key |
| `EPC_API_KEY` | your base64-encoded `email:key` |
| `CALLMEBOT_API_KEY` | your CallMeBot key |
| `WHATSAPP_PHONE` | e.g. `447911123456` |

You do **not** need a `DATABASE_URL` — the app uses SQLite.

### 5d. Trigger a manual test run
1. On your repo → **Actions** tab
2. Click **Scrape London Apartments** in the left sidebar
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch the logs — it should complete in under 5 minutes

### 5e. The cron is now live
The workflow file at `.github/workflows/scrape.yml` runs automatically every 30 minutes. You don't need to do anything else.

To check it's running: **Actions** tab → you'll see a new run appear every ~30 minutes.

---

## How the seen.db cache works

GitHub Actions caches `seen.db` between runs using `actions/cache`. Each run:
1. Restores the latest `seen.db` snapshot from cache
2. Runs the pipeline (only processes listings not already in `seen.db`)
3. Saves the updated `seen.db` back to cache

The cache key includes the run ID so it always writes a fresh snapshot. Cache entries expire after 7 days of non-use — but since the job runs every 30 minutes, this never happens in practice.

---

## Updating your preferences mid-hunt

Just edit `preferences.yaml`, commit, and push:

```bash
# Edit preferences.yaml however you like, then:
git add preferences.yaml
git commit -m "update preferences"
git push
```

The next cron run will use the updated rubric. No need to touch any other files.

---

## Stopping the agent

When you've found your flat:
1. Go to **Actions** → click the workflow → **...** menu → **Disable workflow**

Or delete the repo.

---

## Cost summary

| Service | Free tier | Your usage |
|---|---|---|
| GitHub Actions | 2000 min/month (private repo) | ~720 min/month (48 runs/day × ~15 min/run) |
| Anthropic Claude Haiku | Pay as you go | ~$0.50–2/month |
| TfL API | 500 req/min | Well within limits |
| EPC Register | Unlimited | Free |
| data.police.uk | Unlimited | Free |
| postcodes.io | Unlimited | Free |
| CallMeBot | Free personal use | Free |
| **Total** | | **~$1–2/month** |
