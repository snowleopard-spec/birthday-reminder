"""Export birthdays.txt to birthdays.ics for one-time import into a calendar app.

All-day yearly-recurring events, alarms 3 and 1 days before, free/busy
transparent. UIDs are derived from the name so a re-import updates rather
than duplicates. Output is plaintext PII — birthdays.ics stays gitignored.
"""

import hashlib
from datetime import datetime, timezone

from convert_birthdays import parse_txt

OUTPUT_FILE = "birthdays.ics"
ALARM_DAYS = [3, 1]
# Entries that shouldn't get the "'s Birthday" suffix
TITLE_OVERRIDES = {"Anniversary": "Anniversary"}


def escape(text):
    return text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")


def event(entry, dtstamp):
    date = datetime.strptime(entry["date"], "%Y-%m-%d")
    # Feb 29 entries observe on the 28th, matching reminder.py
    if date.month == 2 and date.day == 29:
        date = date.replace(day=28)
    name = entry["name"]
    title = TITLE_OVERRIDES.get(name, f"{name}'s Birthday")
    uid = hashlib.sha1(name.lower().encode()).hexdigest() + "@birthday-reminder"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART;VALUE=DATE:{date.strftime('%Y%m%d')}",
        "RRULE:FREQ=YEARLY",
        f"SUMMARY:{escape(title)}",
        "TRANSP:TRANSPARENT",
    ]
    for days in ALARM_DAYS:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{escape(title)} in {days} day{'s' if days != 1 else ''}",
            f"TRIGGER;RELATED=START:-P{days}D",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def export():
    entries, errors = parse_txt()
    dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//birthday-reminder//export_ics//EN",
        "CALSCALE:GREGORIAN",
    ]
    for entry in entries:
        lines += event(entry, dtstamp)
    lines.append("END:VCALENDAR")

    with open(OUTPUT_FILE, "w", newline="") as f:
        f.write("\r\n".join(lines) + "\r\n")

    print(f"Done. {len(entries)} events → {OUTPUT_FILE}.")
    if errors:
        print(f"\nSkipped {len(errors)} line(s):")
        for e in errors:
            print(f"  {e}")


if __name__ == "__main__":
    export()
