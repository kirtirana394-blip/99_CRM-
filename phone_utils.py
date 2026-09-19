# phone_utils.py
import re

def clean_phone_number(p):
    """Normalize phone numbers by removing country code 91, spaces, and dashes, leaving clean 10-digit number."""
    if not p or str(p).strip() in ('-', '', 'None', 'nan', 'null'):
        return '-'
    raw = str(p).strip()
    digits = re.sub(r'\D', '', raw)
    if len(digits) == 12 and digits.startswith('91'):
        return digits[2:]
    if len(digits) == 11 and digits.startswith('0'):
        return digits[1:]
    if len(digits) == 13 and digits.startswith('091'):
        return digits[3:]
    if len(digits) > 10 and digits.startswith('91'):
        return digits[2:]
    if len(digits) >= 10:
        return digits[-10:]
    return digits if digits else '-'
