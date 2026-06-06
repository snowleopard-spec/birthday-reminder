import json
import os
import subprocess
from datetime import datetime

INPUT_FILE = "birthdays.txt"
OUTPUT_FILE = "birthdays.json"
DAYS_BEFORE = [3, 1, 0]
PLACEHOLDER_YEAR = 2000

def convert():
    with open(INPUT_FILE, "r") as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    birthdays = []
    errors = []

    for line in lines:
        try:
            name, date_str = [part.strip() for part in line.split(";")]
            date = datetime.strptime(f"{date_str}-{PLACEHOLDER_YEAR}", "%d-%b-%Y")
            birthdays.append({
                "name": name,
                "date": date.strftime(f"{PLACEHOLDER_YEAR}-%m-%d"),
                "days_before": DAYS_BEFORE
            })
        except Exception:
            errors.append(f"  Could not parse: '{line}'")

    birthdays.sort(key=lambda x: x["date"][5:])

    old_contents = None
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r") as f:
            old_contents = f.read()

    new_contents = json.dumps(birthdays, indent=2)

    with open(OUTPUT_FILE, "w") as f:
        f.write(new_contents)

    print(f"Done. {len(birthdays)} birthdays written to {OUTPUT_FILE}.")
    for b in birthdays:
        date = datetime.strptime(b["date"], "%Y-%m-%d")
        print(f"  {date.strftime('%-d %b'):>8}  —  {b['name']}")

    if errors:
        print(f"\nSkipped {len(errors)} line(s) due to errors:")
        for e in errors:
            print(e)

    if new_contents != old_contents:
        sync_to_git()

def sync_to_git():
    answer = input(f"\n{OUTPUT_FILE} changed. Stage, commit, and push to git? [y/N]: ").strip().lower()
    if answer not in ("y", "yes"):
        print("Skipping git sync.")
        return

    try:
        subprocess.run(["git", "add", INPUT_FILE, OUTPUT_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "Update birthdays"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git commit failed: {e}")
        return

    try:
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Git push failed (commit is local): {e}")

if __name__ == "__main__":
    convert()
