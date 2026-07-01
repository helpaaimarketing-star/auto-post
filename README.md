# 🚀 SMMA Automation Bot

**Discord se control hone wala poora Social Media Marketing Agency system.**
Fully automated, 24/7 running, completely FREE to run.

---

## ⚡ Discord Commands (Command Centre)

| Command | Kya karta hai |
|---------|--------------|
| `/scan query niche city country [limit]` | v2 dropdown flow se weak social media leads dhundhta hai |
| `/scrape query niche city country [limit]` | Google Maps se weak social media leads dhundhta hai |
| `/dc business niche city country package price [email]` | Deal close karta hai, Order ID generate karta hai |
| `/build order_id [platform]` | Client ke liye AI-generated post banata hai + download file |
| `/followup business contact channel interest [notes] [due_days]` | Interest tracking + follow-up schedule |
| `/status` | Pipeline stats dashboard dikhata hai |

---

## 🔄 Poora System Flow

```
Step 1:  /scrape  →  Google Maps se weak leads scrape hote hain
                     (jo businesses socials pe inactive hain)
         ↓
Step 2:  Leads #leads-pipeline channel mein aate hain
         Har lead pe 3 buttons hote hain:

         [✅ Approve]     →  AI email generate + auto send via Gmail
         [❌ Skip]        →  Lead skip, Airtable update
         [📢 Direct]      →  Personalised pitch #direct-marketing mein
         ↓
Step 3:  (Manual) Khud client se baat karo
         ↓
Step 4:  /dc  →  Deal close karo, Order ID milta hai
         ↓
Step 5:  /build  →  AI client ki post banata hai
                    📥 Download button #post-downloads mein aata hai
                    .txt file client ko deliver karo
```

---

## 🏗️ Discord Channels (Auto-Create)

Bot khud yeh channels banata hai:

| Channel | Kya aata hai |
|---------|-------------|
| `#leads-pipeline` | Scraped leads with action buttons |
| `#direct-marketing` | Direct outreach pitches |
| `#deal-closed` | Closed deals with Order IDs |
| `#post-builds` | Generated post previews |
| `#post-downloads` | Downloadable .txt files for clients |

---

## 🛠️ Setup (Step by Step)

### Step 1 — Free API Keys Lo

| Service | Free Tier | Link |
|---------|-----------|------|
| **Airtable** | 1,000 records | [airtable.com](https://airtable.com) |
| **Groq AI** | Free forever | [console.groq.com](https://console.groq.com) |
| **SerpAPI** | 100 searches/month | [serpapi.com](https://serpapi.com) |
| **Discord Bot** | Free | [discord.com/developers](https://discord.com/developers) |
| **Gmail SMTP** | Free | [myaccount.google.com](https://myaccount.google.com) |

### Step 2 — Airtable Tables Banao

```bash
python setup_airtable.py
# ya
python -m database.setup_airtable
```

Yeh v2 ke 8 Airtable tables ke exact fields print karega: Raw Dump, Deals,
Post Builds, Email Log, Reports, Follow-ups, Learner Data, Pricing History.

### Step 3 — Environment Variables Set Karo

```bash
cp .env.example .env
# Ab .env file kholo aur sab values bharo
```

### Step 4 — Dependencies Install Karo

```bash
pip install -r requirements.txt
```

### Step 5 — Bot Run Karo

```bash
python main.py
```

Bot terminal mein `SMMA Bot online` dikhayega.

---

## 🏛️ System Architecture (Layered)

```
init.py → main.py
    ↓
input/          listener.py + parser.py + input.py
    ↓
validation/     validator.py + check_duplication.py + auth_validator.py
    ↓
processing/     model_handler.py + data_processor.py + rule_engine.py
    ↓
output/         sender_client.py + action_executor.py + post_processor.py
    ↓
database/       Airtable (DB) + event_log/ (logs)
```

| Folder | Purpose |
|--------|---------|
| `input/` | Discord commands sunna aur parse karna |
| `validation/` | Data check, duplicates, auth |
| `processing/` | AI models, lead scraping, business rules |
| `output/` | Email bhejna, Discord actions, post files |
| `utils/` | Logger, DB client, helpers |
| `library/` | Social checker, order manager |
| `database/` | Airtable setup scripts |
| `tests/` | Unit tests |
| `docs/books/` | Architecture documentation |
| `event_log/` | Runtime logs |

Purane files (`bot.py`, `ai_agent.py`, etc.) backward compatibility ke liye hain — naya entry point `main.py` hai.

---

## 💰 Pricing Strategy (Auto-Suggest)

System khud market rate ke hisaab se pricing suggest karta hai:

| Niche | Starter | Growth | Pro |
|-------|---------|--------|-----|
| Restaurant | $299 | $599 | $999 |
| Dental | $499 | $899 | $1,499 |
| Law | $699 | $1,199 | $1,999 |
| Salon | $249 | $499 | $799 |
| Cafe | $249 | $449 | $749 |

**UK/EU clients ke liye automatically 20% premium add hota hai.**

---

## 🌍 Target Countries

US, UK, Canada, Australia, Germany, France, Netherlands, Sweden,
Norway, Denmark, Finland, Switzerland, Austria, Belgium, Spain,
Italy, Poland, Ireland, New Zealand, Portugal, Czech Republic

---

## 📥 Download Feature

`/build` command ke baad:
- `#post-builds` → Discord embed preview
- `#post-downloads` → **Downloadable `.txt` file** jo seedha client ko de sako

File mein hota hai:
- Full caption
- 30 hashtags
- Business description
- AI image prompt (Midjourney/DALL-E ke liye)
- CTA
- Best posting time
- Tags & keywords

---

## 🔑 Gmail App Password Kaise Milega

1. [myaccount.google.com](https://myaccount.google.com) → Security
2. 2-Step Verification ON karo
3. "App Passwords" click karo
4. App: Mail, Device: Other → Generate
5. 16-character password milega → `.env` mein `GMAIL_APP_PASSWORD` mein daalo

---

## ⚠️ SerpAPI Free Limit

Free plan = 100 searches/month.
Ek scrape = ~4 searches per lead.
25 leads = ~100 searches.
Monthly budget: **1-2 scrape sessions**.

**Tip:** Specific niches + cities target karo, broad queries mat karo.

---

## 🐛 Common Issues

**Bot slash commands nahi dikh rahe?**
→ `DISCORD_GUILD_ID` check karo `.env` mein, bot restart karo.

**Email nahi ja raha?**
→ Gmail App Password use karo, real password nahi. 2FA ON honi chahiye.

**Airtable error?**
→ `AIRTABLE_BASE_ID` `app` se start hona chahiye, `tbl` se nahi.

**SerpAPI 403?**
→ Monthly limit khatam ho gayi. Agla mahina wait karo ya key change karo.

---

*Built for solo SMMA operators. Free forever. Discord se kahi se bhi kaam karo.* 🌍

---

## 🚂 Railway Deploy (24/7 Free Hosting)

### Step 1 — GitHub pe push karo

```bash
git init
git add .
git commit -m "SMMA Bot v1"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/smma-bot.git
git push -u origin main
```

### Step 2 — Railway pe project banao

1. [railway.app](https://railway.app) → **Sign up with GitHub** (free)
2. **New Project** → **Deploy from GitHub repo**
3. Apna `smma-bot` repo select karo
4. Railway automatically build karega

### Step 3 — Environment Variables add karo

Railway dashboard → Apna project → **Variables** tab → Add karein:

```
AIRTABLE_API_KEY        = your_value
AIRTABLE_BASE_ID        = your_value
DISCORD_BOT_TOKEN       = your_value
DISCORD_GUILD_ID        = your_value
GROQ_API_KEY            = your_value
SERPAPI_API_KEY         = your_value
GMAIL_USER              = your_value
GMAIL_APP_PASSWORD      = your_value
ORCHESTRATOR_SECRET     = any_random_string
```

### Step 4 — Deploy!

Variables save karo → Railway automatically redeploy karega.
**Logs tab mein `🟢 SMMA Bot online` dikhega = success.**

### ✅ Bot ab 24/7 Railway pe chal raha hai

Duniya mein kahin se bhi Discord kholo aur commands use karo.
