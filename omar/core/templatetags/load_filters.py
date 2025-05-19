# core/templatetags/load_filters.py
from django import template
import re

register = template.Library()

@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0.0

@register.filter
def extract_date(value):
    """Extracts just the date from a string containing 'Date: YYYY-MM-DD'"""
    if not value:
        return ""
    match = re.search(r'Date:\s*([^,]+)', value)
    if match:
        return match.group(1).strip()
    return ""

@register.filter
def remove_date_phone_email(value):
    """Keeps only the name and address part, removing Date:, Phone:, and Email:"""
    if not value:
        return ""

    # First, clean up any extra spaces or commas
    cleaned = re.sub(r'\s+', ' ', value).strip()

    # Remove Date section and everything after it
    if re.search(r',\s*Date:', cleaned):
        cleaned = re.sub(r',\s*Date:.*$', '', cleaned)

    # If there was no Date, check for Phone section
    elif re.search(r',\s*Phone:', cleaned):
        cleaned = re.sub(r',\s*Phone:.*$', '', cleaned)

    # If there was no Date or Phone, check for Email section
    elif re.search(r',\s*Email:', cleaned):
        cleaned = re.sub(r',\s*Email:.*$', '', cleaned)

    return cleaned.strip()

@register.filter
def index(value, arg):
    """
    Returns the item at the given index in the list.
    """
    try:
        return value[int(arg)]
    except (IndexError, TypeError, ValueError):
        return ""    
