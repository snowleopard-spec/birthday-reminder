# Rotating `BIRTHDAY_CIPHER_PASSPHRASE`

The passphrase re-derives the Fernet key on every run. To rotate, you re-encrypt the blob with a new passphrase and update every place the old one lives ([[birthday-upgrade-plan]] lists them: password manager, laptop `.env`, droplet `.env`).

**Prep — pick a low-risk time window.** The droplet cron fires at 22:30 UTC (06:30 SGT). Do the swap well outside that window so a mid-rotation cron doesn't hit a mismatched blob/`.env` and fail. Any other time of day is fine.

## Procedure

### 1. Generate + stash new passphrase
```bash
openssl rand -base64 32
```
Save the output to the password manager entry **immediately**. If you lose it before finishing step 3 (below), you can still recover — the *old* passphrase still opens the current blob until you overwrite it.

### 2. Re-encrypt on laptop
`convert_birthdays.py` reads `birthdays.txt` (plaintext source of truth) and encrypts with whatever passphrase is in the env. So:
```bash
cd /Users/wessch/Projects/Stack/birthday
$EDITOR .env                              # replace BIRTHDAY_CIPHER_PASSPHRASE=<new>
set -a && . ./.env && set +a
python convert_birthdays.py               # writes birthdays.json.enc, offers to commit + push
```
Answer **yes** to the commit + push prompt. The new blob is now on `origin/main`.

### 3. Update droplet `.env` + pull
```bash
ssh root@161.35.122.12
cd /root/birthday
$EDITOR .env                              # replace BIRTHDAY_CIPHER_PASSPHRASE=<new>
git pull                                  # fetch the newly-encrypted blob
```
Order matters: `.env` first, then `git pull`. If pull ran first and cron fired in the gap, it would try to decrypt the new blob with the old passphrase and error.

### 4. Verify
```bash
set -a && . ./.env && set +a && ./venv/bin/python reminder.py
```
Expect: full birthday list printed, and either `0 email(s) sent, 0 failed` or the appropriate send count. Any decrypt error means blob/passphrase mismatch — recheck `.env`.

### 5. Confirm password manager
Re-open the password manager entry and paste-test it against the running droplet before considering the rotation done.

## If something goes wrong mid-rotation

The old passphrase still decrypts the last blob on `origin/main` up until step 2's push. If you have to abort:
- **Before step 2 push** — nothing changed anywhere; just restore old value in laptop `.env`.
- **After step 2 push, before step 3** — either finish step 3 quickly, or `git revert` the new-blob commit on `main` and push, which restores the old blob for the old passphrase.
- **After step 3** — you're done; the rotation succeeded.

## What this does *not* rotate

- **`RESEND_API_KEY`** — separate credential in both `.env` files. Rotate via the Resend dashboard if compromised; procedure is the same shape (update laptop `.env`, update droplet `.env`, no re-encrypt needed).
- **Old blob commits in git history** — every prior blob remains in history, still openable by the old passphrase. That's fine: the *contents* were only ever the birthday list, and history-rewrite is disruptive. Only rotate history if the *plaintext* leaks, not for passphrase hygiene.
