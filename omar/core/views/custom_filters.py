from django import template
import re

register = template.Library()

@register.filter
def extract_date(value):
    match = re.search(r'Date: ([^,]+)', value)
    return match.group(1) if match else 'N/A'

@register.filter
def extract_address(value):
    match = re.search(r'<strong>.*?</strong>(.*?)(?:, Date:|$)', value)
    return match.group(1).strip() if match else value
