from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Template filter to get a value from a dictionary using a variable as key."""
    if not isinstance(dictionary, dict):
        return 0
    return dictionary.get(key, 0)
