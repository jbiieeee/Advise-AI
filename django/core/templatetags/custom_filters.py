from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def replace(value, arg):
    """
    Replaces characters in a string.
    Usage: {{ string|replace:"_, " }}
    """
    if not value:
        return ""
    parts = arg.split(',')
    if len(parts) != 2:
        return value
    old = parts[0].strip()
    new = parts[1].strip()
    return str(value).replace(old, new)
