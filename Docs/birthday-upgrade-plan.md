# birthday-reminder — Encrypt-at-Rest + Droplet Migration Plan

Standalone plan. Turns the reminder into: names encrypted at rest (Fernet + scrypt), committed only as ciphertext, decrypted **in memory** during a droplet cron run. Retires GitHub Actions. Purges the 42 plaintext names from git history.

**Golden ordering rule:** finish all commit work and get to a single final state on `main` *before* rewriting history. `git filter-repo` rewrites every branch at once — running it with an unmerged feature branch in flight corrupts the merge. So: **merge first, purge second.**

Full sequence: build branch → merge to main → encrypt + commit blob → purge history → force-push → deploy.

---

## Progress (as of 2026-07-21)

- [x] **Step 1** — feature branch built and committed (`c81597e` on `encrypt-at-rest`, later rewritten to `1560055` by filter-repo)
- [x] **Step 2** — fast-forward merged to `main`
- [x] **Step 3** — passphrase generated + saved to password manager, `birthdays.json.enc` written and committed (`81f76b3`, later rewritten to `38535bd`)
- [x] **Step 4** — `--mirror` backup taken at `../birthday-backup.git`, `git-filter-repo` purged `birthdays.json` + `birthdays.txt` from every commit, origin re-added
- [x] **Step 5** — force-pushed `main` to `origin` (only `main`; `encrypt-at-rest` local branch left un-pushed as merged clutter). Remote HEAD is `38535bd`. No tags.
- [x] **Step 6** — droplet deploy complete (2026-07-23). HTTPS clone at `/root/birthday`, venv installed, `.env` at `0600`, manual `reminder.py` run printed the list and reported `0 email(s) sent, 0 failed` (correct — no birthdays match today). Cron installed via `crontab -e` at `0 23 * * *` logging to `/root/birthday/cron.log`. 6a hardening checks **skipped by user** — droplet already known-good from bonzai/sonar/dilithium/smallcap-momentum.
- [x] **Cleanup — first scheduled run verified** — 23:00 UTC 2026-07-23 run present in `/root/birthday/cron.log`, ended `Done. 0 email(s) sent, 0 failed` (expected — Faye at 8 days is next, not in `[3,1,0]`).
- [x] **Schedule shifted** — cron changed from `0 23 * * *` to `30 22 * * *` UTC (06:30 SGT) at user's request on 2026-07-24.
- [x] **Cleanup — GitHub Actions secrets** — `RESEND_API_KEY`, `TO_EMAIL`, `FROM_EMAIL` deleted via `gh secret delete` on 2026-07-24. `gh secret list` returns empty.
- [ ] **(Optional)** GitHub Support ticket to expire cached commit SHAs sooner than the ~90-day default. Verified 0 forks, 1 self-star, 0 external watchers.

**Backup decision:** the `--mirror` backup at `/Users/wessch/Projects/Stack/birthday-backup.git` is being **kept** by user preference. It contains the 42 plaintext names but is local-only, never synced. Not deleted.

**Where you left off:** deploy is live, first scheduled run verified, cron runs at 22:30 UTC daily = 06:30 SGT, Actions secrets deleted, laptop `.env` in place. Only two optional items remain: disable Actions on the repo, and the GH Support ticket for SHA expiry.

**Related runbook:** `Docs/rotate-passphrase.md` — procedure for rotating `BIRTHDAY_CIPHER_PASSPHRASE` if ever needed.

---

## Prerequisites / decisions

1. **Is this repo cloned anywhere besides your machine + GitHub?** (another laptop, the droplet already?) Force-pushing rewritten history breaks every other clone — they must re-clone, not `git pull`. If the droplet isn't set up yet, you're clean.
2. **Passphrase is permanent and load-bearing.** It re-derives the key on every run; the ciphertext can only be opened by re-supplying it. Save it in your password manager at creation. Lose it and `birthdays.json.enc` is permanently unreadable — there's no recovery path for a lost symmetric key.
3. **The droplet only becomes a privacy win once hardened** (see Step 6). Encryption protects the *public repo* and the *stolen-disk* case; it does nothing against live root on the box. SSH hardening is the priority.
4. **GitHub-side residue after force-push.** The repo is public; verified via API as of 2026-07-21: **0 forks, 1 star (self), 0 external watchers**. No fork copies exist to worry about. However, force-push does *not* immediately purge the old commits from GitHub — for roughly 90 days they remain reachable by SHA at `github.com/snowleopard-spec/birthday-reminder/commit/<sha>` if anyone still has one. Assumption we're accepting: nobody scraped the SHAs. If you want the belt-and-braces version, open a support ticket after the force-push asking GitHub to expire the cached views. Otherwise, live with the 90-day window.

---

## Step 1 — Build the feature branch (local) ✅ DONE

```bash
git checkout -b encrypt-at-rest
```

### 1a · Crypto module — `birthday_crypto.py` (new)
```python
import base64, json, os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

def _key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1)   # memory-hard KDF
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))

def encrypt(data: dict, passphrase: str) -> bytes:
    salt = os.urandom(16)                                   # fresh salt per encrypt
    token = Fernet(_key(passphrase, salt)).encrypt(json.dumps(data).encode())
    return salt + token                                     # salt rides with ciphertext

def decrypt(blob: bytes, passphrase: str) -> dict:
    salt, token = blob[:16], blob[16:]
    return json.loads(Fernet(_key(passphrase, salt)).decrypt(token))
```

### 1b · Rewrite `convert_birthdays.py` — txt → .enc directly

Local source of truth stays `birthdays.txt` (human-readable, gitignored). The script parses it, encrypts, writes `birthdays.json.enc`, and offers to commit + push the `.enc`. No plaintext `.json` is ever written to disk. No separate `encrypt_*.py` — this one script owns the whole edit-and-publish flow.

```python
import json, os, subprocess
from datetime import datetime
import birthday_crypto

INPUT_FILE = "birthdays.txt"
OUTPUT_FILE = "birthdays.json.enc"
DAYS_BEFORE = [3, 1, 0]
PLACEHOLDER_YEAR = 2000

def parse_txt():
    with open(INPUT_FILE) as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    entries, errors = [], []
    for line in lines:
        try:
            name, date_str = [p.strip() for p in line.split(";")]
            date = datetime.strptime(f"{date_str}-{PLACEHOLDER_YEAR}", "%d-%b-%Y")
            entries.append({
                "name": name,
                "date": date.strftime(f"{PLACEHOLDER_YEAR}-%m-%d"),
                "days_before": DAYS_BEFORE,
            })
        except Exception:
            errors.append(line)
    entries.sort(key=lambda x: x["date"][5:])
    return entries, errors

def convert():
    pp = os.environ.get("BIRTHDAY_CIPHER_PASSPHRASE")
    if not pp:
        raise SystemExit("Set BIRTHDAY_CIPHER_PASSPHRASE first")

    entries, errors = parse_txt()

    old_blob = open(OUTPUT_FILE, "rb").read() if os.path.exists(OUTPUT_FILE) else None
    new_blob = birthday_crypto.encrypt(entries, pp)

    # Skip write+push if roundtrip-decrypt of the old blob matches new entries.
    # (Fresh salt per encrypt means new_blob != old_blob every time, so byte-compare would churn.)
    changed = True
    if old_blob is not None:
        try:
            changed = birthday_crypto.decrypt(old_blob, pp) != entries
        except Exception:
            changed = True  # can't read old — treat as changed

    with open(OUTPUT_FILE, "wb") as f:
        f.write(new_blob)

    print(f"Done. {len(entries)} birthdays encrypted → {OUTPUT_FILE}.")
    for b in entries:
        d = datetime.strptime(b["date"], "%Y-%m-%d")
        print(f"  {d.strftime('%-d %b'):>8}  —  {b['name']}")
    if errors:
        print(f"\nSkipped {len(errors)} line(s):")
        for e in errors: print(f"  {e}")

    if changed:
        sync_to_git()
    else:
        print("\nNo content change — skipping git sync.")

def sync_to_git():
    ans = input(f"\n{OUTPUT_FILE} changed. Stage, commit, and push? [y/N]: ").strip().lower()
    if ans not in ("y", "yes"):
        print("Skipping git sync.")
        return
    try:
        subprocess.run(["git", "add", OUTPUT_FILE], check=True)   # ONLY the .enc
        subprocess.run(["git", "commit", "-m", "Update birthdays"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git step failed: {e}")

if __name__ == "__main__":
    convert()
```

Note the `git add birthdays.json.enc` is explicit — never `git add .` — so a stray plaintext file can't slip in even if you forget to gitignore something.

### 1c · `reminder.py` — decrypt in memory
Replace the plaintext load with:
```python
import birthday_crypto, os
passphrase = os.environ.get("BIRTHDAY_CIPHER_PASSPHRASE")
if not passphrase:
    raise ValueError("BIRTHDAY_CIPHER_PASSPHRASE must be set")
with open("birthdays.json.enc", "rb") as f:
    birthdays = birthday_crypto.decrypt(f.read(), passphrase)
```
Decrypt straight into the variable — never write plaintext to a temp file.

### 1d · Feb-29 crash guard (same file)
Both `days_until_birthday` and `format_email` do `bday.replace(year=...)`, which raises on Feb 29 in a non-leap year (2027 is next). Add and use:
```python
def _this_years_occurrence(bday, year):
    try:
        return bday.replace(year=year)
    except ValueError:                 # Feb 29 in a non-leap year
        return bday.replace(year=year, day=28)
```
Apply at every `.replace(year=...)` call site (current-year and next-year branches in both functions).

### 1e · Resilient send loop (same file)
Wrap the per-person `resend.Emails.send(...)` in `try/except`, log the failure, and `continue`, so one failed send doesn't abort reminders for everyone after them.

### 1f · Housekeeping
- `.gitignore`: add `birthdays.json` and `birthdays.txt`. The `.enc` blob **is** committed. `birthdays.txt` stays as your local, human-readable source of truth — the droplet never sees it.
- `requirements.txt`: add `cryptography>=43`.
- Delete `.github/workflows/daily_check.yml` (Actions retired).
- `README.md`: document the encrypted-blob model and the edit workflow (edit `birthdays.txt` → `python convert_birthdays.py` → it encrypts and offers to commit + push the `.enc`).

**Test before merging:**
```bash
python -c "import birthday_crypto as c; b=c.encrypt({'x':1},'pw'); assert c.decrypt(b,'pw')=={'x':1}; print('roundtrip ok')"
```
Also confirm: wrong passphrase raises; `reminder.py` errors clearly when the passphrase env is unset; a `2000-02-29` entry evaluated against 2027 doesn't raise.

```bash
git add birthday_crypto.py convert_birthdays.py reminder.py .gitignore requirements.txt README.md
git rm .github/workflows/daily_check.yml
git commit -m "feat: encrypt birthdays at rest (Fernet+scrypt), decrypt in memory, retire Actions, Feb-29 guard, resilient send"
```

---

## Step 2 — Merge to main (local) ✅ DONE

```bash
git checkout main
git merge encrypt-at-rest
```
`main` now holds the final code state. Do not purge history yet — the blob isn't committed.

---

## Step 3 — Encrypt + commit the blob ✅ DONE

```bash
export BIRTHDAY_CIPHER_PASSPHRASE="$(openssl rand -base64 32)"   # SAVE THIS in a password manager
python convert_birthdays.py                                     # reads birthdays.txt → writes birthdays.json.enc
```
`convert_birthdays.py` only stages `birthdays.json.enc` and will offer to commit + push. Say **no** to the push prompt here — we still need to purge history (Step 4) before anything hits GitHub. Just take the local commit:
```bash
# if you declined the script's push prompt and it also skipped commit, do it manually:
git add birthdays.json.enc
git commit -m "add encrypted birthday blob"
```
(The plaintext may still exist in earlier commits — Step 4 wipes it. Don't worry about whether it slipped into a local commit; the purge cleans it regardless.)

---

## Step 4 — Purge plaintext from history ✅ DONE

**Executed note:** backup is at `/Users/wessch/Projects/Stack/birthday-backup.git` (not `../birthday-reminder-backup.git` — repo dir is `birthday`, not `birthday-reminder`). `filter-repo --force` was used because the repo was not a fresh clone. All commit SHAs rotated (expected). Verified: full-history grep for plaintext names returned zero matches; `git log --all -- birthdays.json birthdays.txt` empty.


**Backup first** (this backup contains the plaintext — see caveat below):
```bash
cd ..
git clone --mirror birthday-reminder birthday-reminder-backup.git
cd birthday-reminder
```
Purge:
```bash
pip install git-filter-repo
git filter-repo --path birthdays.json --path birthdays.txt --invert-paths
```
filter-repo removes the `origin` remote on purpose. Re-add it:
```bash
git remote add origin git@github.com:snowleopard-spec/birthday-reminder.git
```
Verify:
```bash
git log --all -- birthdays.json birthdays.txt      # should print nothing
```

---

## Step 5 — Force-push ✅ DONE

**Executed as:** `git push origin --force main` — only `main` was pushed. `--all` was skipped because the local `encrypt-at-rest` branch is merged clutter that doesn't need to appear on origin. No tags in the repo, so `--force --tags` was moot. Remote HEAD is now `38535bd`.

Original plan commands (for reference — do not re-run):
```bash
git push origin --force --all
git push origin --force --tags
```

---

## Step 6 — Deploy to droplet ⏸ PENDING

**Target droplet:** `unicorn-hunt` (Ubuntu, Python 3.12.3, 48G disk / 1.9G RAM / 2G swap). Already hosts bonzai, sonar, dilithium, smallcap-momentum. Ample headroom for a once-a-day cron.

**Convention chosen:** match the box. Birthday lives at `/root/birthday/`, runs as **root**, like bonzai and sonar. The `.env` at `chmod 600` still keeps the passphrase out of any non-root process. If you ever want to shift it to a non-root user later, it's a `useradd + chown + chmod` away — not worth doing preemptively.

**What you need before starting:**
- `BIRTHDAY_CIPHER_PASSPHRASE` retrieved from your password manager.
- Your Resend API key.
- The recipient email (`TO_EMAIL`) and sender address (`FROM_EMAIL`, e.g. `onboarding@resend.dev`).
- SSH access to `root@unicorn-hunt`.

### 6a · Verify existing hardening (don't re-do — just confirm)

The box has been running production apps for a while. Presumably it's already in a good state. Just run these checks and only remediate if something looks off. Don't blanket-apply hardening that could break existing apps.

```bash
# SSH — confirm password auth is off and (typically) root login is via key only
sudo sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin|pubkeyauthentication)'
# want:  passwordauthentication no
#        permitrootlogin  either "prohibit-password" (key-only) or "no"
#        pubkeyauthentication yes

# ufw — is it active, and what does it allow?
sudo ufw status verbose
# expect: active, with 22 (SSH), plus whatever bonzai/sonar/dilithium/smallcap need

# unattended-upgrades — enabled and doing something?
systemctl is-enabled unattended-upgrades
sudo cat /etc/apt/apt.conf.d/20auto-upgrades   # both lines should be "1"

# Existing cron entries — see what else runs on this box before adding your own
crontab -l
```

If any of the above surprises you, fix it first — but you probably don't need to. Not a blocker for the deploy either way; it protects the box, not the encrypted blob.

**Disk-at-rest:** DO droplets don't encrypt `/dev/vda1` by default and adding it to a live box is a big change. Skip. The blob is encrypted; the `.env` passphrase is the residual risk, and its safety is the login being hard to breach — which is what 6a verifies.

### 6b · Deploy

Clone over HTTPS (public repo, no auth needed). Cron does **not** pull; when you push a new list, you'll SSH in and `git pull` manually.

```bash
ssh root@unicorn-hunt
cd /root
git clone https://github.com/snowleopard-spec/birthday-reminder.git birthday
cd birthday
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Create `.env` in `/root/birthday/`:
```
BIRTHDAY_CIPHER_PASSPHRASE=...   # from your password manager (generated in Step 3)
RESEND_API_KEY=...
TO_EMAIL=...
FROM_EMAIL=...
```
```bash
chmod 600 .env
```

Sanity-check a manual run before scheduling:
```bash
cd /root/birthday && set -a && . ./.env && set +a && ./venv/bin/python reminder.py
```
You should see the full list printed with days-until values, and either an email sent (if today matches someone's `days_before`) or "0 email(s) sent". If it errors, fix before adding cron.

Cron — no `git pull`, secrets from `.env` (not inline so `crontab -l` doesn't leak them). `23:00 UTC = 07:00 SGT next day`:
```bash
( crontab -l 2>/dev/null; echo '0 23 * * * cd /root/birthday && set -a && . ./.env && set +a && ./venv/bin/python reminder.py >> /root/birthday/cron.log 2>&1' ) | crontab -
```
The `>> cron.log 2>&1` gives you a paper trail — check it after the first scheduled run to confirm.

Verify the crontab took:
```bash
crontab -l | grep birthday
```

---

## Caveats to hold in mind

- **The `--mirror` backup from Step 4 contains the 42 names in plaintext.** Keep it off any synced/cloud location and delete it once the force-push is confirmed and the droplet run works. Don't let the safety net become the leak.
- **Force-push breaks other clones.** Anyone/anything that cloned the old history must re-clone fresh. (The droplet clones *after* the push, in Step 6, so it's fine.)
- **The `.env` passphrase is plaintext at rest** — unavoidable for an unattended job. Its safety = your server's login being hard to breach (Step 6a) + disk encryption for the theft case. Encryption of the blob protects the *public repo*, not the box.
- **Changing the passphrase later is a re-key, not a setting:** decrypt the blob with the old one, re-encrypt with the new one, commit the new blob. Pick a strong random one now and you shouldn't need to.

---

## Where the passphrase lives

Three places it can exist, by design:

| Location | Persistence | Purpose |
|---|---|---|
| Password manager | Permanent, encrypted | Canonical copy. If lost, blob is unrecoverable. |
| `/root/birthday/.env` on droplet (`chmod 600`) | Persistent, plaintext on disk | Cron sources this to decrypt at runtime. Created in Step 6b. |
| `/Users/wessch/Projects/Stack/birthday/.env` on laptop (`chmod 600`) | Persistent, plaintext on disk | **Optional convenience** so you don't `export` every time you edit `birthdays.txt`. Already gitignored. See below. |

The laptop `.env` is a trade-off: one more copy on disk vs. never having to paste the passphrase into a terminal. Most devs keep it. To create it:
```bash
cat > /Users/wessch/Projects/Stack/birthday/.env <<'EOF'
BIRTHDAY_CIPHER_PASSPHRASE=<paste from password manager>
EOF
chmod 600 .env
```

---

## Editing the birthday list later

On your laptop — `birthdays.txt` is your local source of truth (gitignored, never leaves the box):
```bash
cd /Users/wessch/Projects/Stack/birthday
# option A — if you created the local .env above:
set -a && . ./.env && set +a
# option B — if not, paste the passphrase every time:
export BIRTHDAY_CIPHER_PASSPHRASE="..."

$EDITOR birthdays.txt                     # add / edit / remove lines
python convert_birthdays.py               # encrypts → birthdays.json.enc, offers to commit + push
```
Then, on the droplet, one manual pull to pick up the new blob:
```bash
ssh root@unicorn-hunt
cd /root/birthday && git pull
```
Next cron run at 07:00 SGT uses the new list. No plaintext ever leaves your laptop.

---

## Checklist

- [x] Feature branch built, tested, roundtrip passes
- [x] Merged to main
- [x] Passphrase generated **and saved to password manager**
- [x] `birthdays.json.enc` committed; plaintext gitignored + unstaged
- [x] `--mirror` backup taken (at `/Users/wessch/Projects/Stack/birthday-backup.git`)
- [x] History purged; `git log --all -- birthdays.json birthdays.txt` empty
- [x] Force-pushed `main` (no tags in repo; encrypt-at-rest branch not pushed)
- [~] Droplet hardening verified — **skipped by user**; box already known-good from existing production apps
- [x] Deployed at `/root/birthday` on `unicorn-hunt`: HTTPS clone, venv installed, `.env` at `0600`, manual `reminder.py` run works
- [x] Cron installed: originally `0 23 * * *`, retimed 2026-07-24 to `30 22 * * *` UTC (06:30 SGT); sources `.env`, logs to `/root/birthday/cron.log`
- [x] Manual droplet run completes without error (`0 email(s) sent, 0 failed` — nobody's birthday matched today, expected)
- [x] First scheduled run verified — 23:00 UTC 2026-07-23 run present in `/root/birthday/cron.log`
- [~] `--mirror` backup deleted — **kept** by user preference (local-only, contains plaintext but not synced)
- [x] Delete GitHub Actions secrets: `RESEND_API_KEY`, `TO_EMAIL`, `FROM_EMAIL` — done 2026-07-24 via `gh secret delete`.
- [ ] (Optional) Disable Actions on the repo entirely (Settings → Actions → General → "Disable Actions") — removes attack surface, tidies the UI.
- [x] Create `/Users/wessch/Projects/Stack/birthday/.env` on laptop with `BIRTHDAY_CIPHER_PASSPHRASE`, `chmod 600` — done 2026-07-24.
- [ ] (Optional) GitHub Support ticket filed to expire cached commits by SHA — otherwise accept the ~90-day residue window
