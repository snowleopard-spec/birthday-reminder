# Birthday Reminder

Emails you a few days before — and on — each person's birthday. Names are
**encrypted at rest** with a passphrase-derived key (Fernet + scrypt); only
the ciphertext blob (`birthdays.json.enc`) is ever committed. The reminder
job decrypts in memory on a hardened droplet under cron. Nothing plaintext
leaves your laptop.

---

## Files

```
birthday/
├── birthdays.txt              ← local, human-readable source of truth (gitignored)
├── birthdays.json.enc         ← encrypted blob (committed, safe in public repo)
├── birthday_crypto.py         ← Fernet + scrypt encrypt/decrypt
├── convert_birthdays.py       ← birthdays.txt → birthdays.json.enc, offers commit + push
├── reminder.py                ← decrypts in memory, sends reminders
├── requirements.txt
└── README.md
```

`birthdays.txt` format — one entry per line: `Name; DD-MMM` (e.g. `Alice; 24-Mar`).
Lines starting with `#` are ignored.

---

## Setup (one-time)

### 1. Install
```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
```

### 2. Generate and save a passphrase
```bash
openssl rand -base64 32
```
**Save this in your password manager immediately.** It re-derives the key on
every run; lose it and the blob is permanently unreadable.

### 3. Get a Resend API key
Sign up at [resend.com](https://resend.com), create an API key, and use
`onboarding@resend.dev` as the from-address (works without domain
verification but only sends to your own verified email).

### 4. Create your `birthdays.txt` and encrypt it
```bash
export BIRTHDAY_CIPHER_PASSPHRASE="..."   # from your password manager
$EDITOR birthdays.txt                      # add entries
python convert_birthdays.py                # writes birthdays.json.enc
```

### 5. Deploy to a droplet
See `birthday-upgrade-plan.md` for the full droplet setup (SSH hardening,
non-root user, `.env` with `chmod 600`, cron). Summary:

- Clone the repo over HTTPS on the droplet.
- Put secrets in `/opt/birthday-reminder/.env` (`BIRTHDAY_CIPHER_PASSPHRASE`,
  `RESEND_API_KEY`, `TO_EMAIL`, `FROM_EMAIL`), `chmod 600`.
- Cron entry (`23:00 UTC = 07:00 SGT`):
  ```
  0 23 * * * cd /opt/birthday-reminder && set -a && . ./.env && set +a && ./venv/bin/python reminder.py
  ```

---

## Editing the birthday list later

On your laptop:
```bash
export BIRTHDAY_CIPHER_PASSPHRASE="..."
$EDITOR birthdays.txt
python convert_birthdays.py       # re-encrypts, offers to commit + push
```

Then on the droplet, one manual pull to pick up the new blob:
```bash
ssh birthdaybot@<droplet>
cd /opt/birthday-reminder && git pull
```

Next cron run uses the new list. No plaintext ever leaves your laptop.

---

## Customising reminder timing

Each entry gets a default `days_before = [3, 1, 0]` (three days out, day
before, day of). To customise per-person, edit `birthdays.json.enc` via a
decrypt/re-encrypt loop, or extend `convert_birthdays.py` to parse a
per-line override.

---

## How it works

At 07:00 SGT the droplet:
1. Reads `birthdays.json.enc`
2. Derives the key from `BIRTHDAY_CIPHER_PASSPHRASE` via scrypt
3. Decrypts in memory
4. For each person, computes days-until-birthday and emails if today matches
   their `days_before` list
