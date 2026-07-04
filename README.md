# Birthday Reminder

Emails you a few days before — and on — each person's birthday. Runs daily via GitHub Actions. Nothing stored in the cloud except your code.

---

## Setup (one-time, ~15 minutes)

### 1. Create a private GitHub repo
- Go to github.com → New repository
- Name it `birthday`
- Set to **Private**
- Don't initialise with any files

### 2. Push these files to the repo
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/birthday.git
git push -u origin main
```

### 3. Get a Resend API key
- Sign up at [resend.com](https://resend.com) (free)
- Go to API Keys → Create API Key
- Copy the key (you only see it once)
- For the sending address, use `onboarding@resend.dev` initially —
  this works immediately without domain verification, but only sends to
  your own verified email address (fine for personal use)

### 4. Add secrets to GitHub
In your repo: **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Name | Value |
|------|-------|
| `RESEND_API_KEY` | Your Resend API key |
| `TO_EMAIL` | The email address you want reminders sent to |
| `FROM_EMAIL` | `onboarding@resend.dev` (or your verified domain later) |

### 5. Edit birthdays.txt
Add entries to `birthdays.txt` — one per line, `Name; DD-MMM` (e.g. `Alice; 24-Mar`).
Then run:
```bash
python3 convert_birthdays.py
```
This regenerates `birthdays.json` (sorted by date, with default reminders) and, if
the JSON actually changed, prompts to stage, commit, and push both files to git.

Prefer to edit JSON directly? Format:
```json
{
  "name": "Person's name",
  "date": "YYYY-MM-DD",      ← year doesn't matter for logic, just use real birth year
  "days_before": [7, 1, 0]   ← send reminders 7 days before, 1 day before, and on the day
}
```

### 6. Test it manually
- Go to your repo → **Actions** tab
- Click **Daily Birthday Check** → **Run workflow**
- Watch the logs — you should see each person listed with days remaining
- If anyone hits a reminder threshold, you'll get an email

---

## How it works

The script runs every morning at 07:00 Singapore time. It:
1. Reads `birthdays.json`
2. Calculates how many days until each person's next birthday
3. Sends an email for anyone whose `days_before` list includes today's countdown

That's it.

---

## Customising reminder timing

Each person can have their own `days_before` list. For example:
- `[14, 7, 3, 1, 0]` — two weeks out, one week, three days, day before, day of
- `[7, 0]` — just a week's notice and the day itself
- `[1, 0]` — last-minute only

---

## File structure

```
birthday/
├── .github/
│   └── workflows/
│       └── daily_check.yml   ← the scheduler
├── birthdays.txt              ← human-friendly source list
├── birthdays.json             ← generated data (stays private in private repo)
├── convert_birthdays.py       ← txt → json, with optional git sync
├── reminder.py                ← the logic
├── requirements.txt
└── README.md
```
