import json
from datetime import datetime

INPUT_FILE = "birthdays.txt"
OUTPUT_FILE = "birthdays.json"
DAYS_BEFORE = [7, 1, 0]
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

    with open(OUTPUT_FILE, "w") as f:
        json.dump(birthdays, f, indent=2)

    print(f"Done. {len(birthdays)} birthdays written to {OUTPUT_FILE}.")
    for b in birthdays:
        date = datetime.strptime(b["date"], "%Y-%m-%d")
        print(f"  {date.strftime('%-d %b'):>8}  —  {b['name']}")

    if errors:
        print(f"\nSkipped {len(errors)} line(s) due to errors:")
        for e in errors:
            print(e)

if __name__ == "__main__":
    convert()
