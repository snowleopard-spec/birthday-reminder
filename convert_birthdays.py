import os
import subprocess
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

    # Fresh salt per encrypt means byte-comparing blobs would churn every run.
    # Compare against the roundtrip-decrypted old blob instead.
    changed = True
    if os.path.exists(OUTPUT_FILE):
        try:
            old = birthday_crypto.decrypt(open(OUTPUT_FILE, "rb").read(), pp)
            changed = old != entries
        except Exception:
            changed = True

    with open(OUTPUT_FILE, "wb") as f:
        f.write(birthday_crypto.encrypt(entries, pp))

    print(f"Done. {len(entries)} birthdays encrypted → {OUTPUT_FILE}.")
    for b in entries:
        d = datetime.strptime(b["date"], "%Y-%m-%d")
        print(f"  {d.strftime('%-d %b'):>8}  —  {b['name']}")
    if errors:
        print(f"\nSkipped {len(errors)} line(s):")
        for e in errors:
            print(f"  {e}")

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
        subprocess.run(["git", "add", OUTPUT_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update birthdays"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git step failed: {e}")


if __name__ == "__main__":
    convert()
