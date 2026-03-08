import json
import os
import resend
from datetime import datetime
from zoneinfo import ZoneInfo

SGT = ZoneInfo("Asia/Singapore")


def days_until_birthday(birthday_str: str) -> int:
    """Calculate how many days until the next occurrence of a birthday."""
    today = datetime.now(SGT).date()
    bday = datetime.strptime(birthday_str, "%Y-%m-%d").date()

    next_bday = bday.replace(year=today.year)
    if next_bday < today:
        next_bday = bday.replace(year=today.year + 1)

    return (next_bday - today).days


def format_email(name: str, days: int, birthday_str: str) -> tuple[str, str]:
    """Return (subject, html_body) for the reminder email."""
    today = datetime.now(SGT).date()
    bday = datetime.strptime(birthday_str, "%Y-%m-%d").date()

    # Use the actual upcoming birthday date for the correct day name and year
    next_bday = bday.replace(year=today.year)
    if next_bday < today:
        next_bday = bday.replace(year=today.year + 1)
    date_str = next_bday.strftime("%A %-d %B")  # e.g. "Sunday 8 March"

    if days == 0:
        subject = f"🎂 Today is {name}'s birthday!"
        headline = f"Today is {name}'s birthday! ({date_str})"
        body_line = "Don't let the day go by without reaching out."
    elif days == 1:
        subject = f"⏰ {name}'s birthday is tomorrow"
        headline = f"{name}'s birthday is tomorrow ({date_str})"
        body_line = "Last chance to sort a message, call, or gift."
    else:
        subject = f"🗓️ {name}'s birthday is in {days} days"
        headline = f"{name}'s birthday is in {days} days ({date_str})"
        body_line = "Plenty of time to plan something."

    html = f"""
    <div style="font-family: Georgia, serif; max-width: 480px; margin: 0 auto; padding: 32px; color: #2c2c2c;">
        <h2 style="margin-top: 0; color: #1a1a1a;">{headline}</h2>
        <p style="font-size: 16px; line-height: 1.6;">{body_line}</p>
        <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 24px 0;">
        <p style="font-size: 12px; color: #999;">Sent by your birthday reminder bot.</p>
    </div>
    """
    return subject, html


def main():
    api_key = os.environ.get("RESEND_API_KEY")
    to_email = os.environ.get("TO_EMAIL")
    from_email = os.environ.get("FROM_EMAIL", "birthdays@resend.dev")

    if not api_key or not to_email:
        raise ValueError("RESEND_API_KEY and TO_EMAIL must be set as environment variables.")

    resend.api_key = api_key

    with open("birthdays.json", "r") as f:
        birthdays = json.load(f)

    sent_count = 0

    for person in birthdays:
        name = person["name"]
        birthday = person["date"]
        remind_days = person.get("days_before", [7, 1, 0])

        days = days_until_birthday(birthday)
        print(f"{name}: {days} days away")

        if days in remind_days:
            subject, html = format_email(name, days, birthday)
            resend.Emails.send({
                "from": from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
            })
            print(f"  ✓ Reminder sent: '{subject}'")
            sent_count += 1

    print(f"\nDone. {sent_count} email(s) sent.")


if __name__ == "__main__":
    main()
