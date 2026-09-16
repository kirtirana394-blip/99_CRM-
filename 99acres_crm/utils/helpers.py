from datetime import datetime
import re

def normalize_phone(value):
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits or None

def normalize_email(value):
    if not value:
        return None
    return str(value).strip().lower() or None

def parse_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None

def fmt_date(value):
    return value.strftime("%d/%m/%Y") if value else ""

def current_user_id(session):
    return session.get("user_id")
