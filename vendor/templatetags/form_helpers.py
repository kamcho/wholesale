from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get a value from a dictionary by key"""
    return dictionary.get(key)

@register.filter
def get_field_id(field):
    """Get the ID of a form field"""
    return field.id_for_label

@register.filter
def get_quantity_field(form, variation):
    """Get the quantity field for a specific variation"""
    return form[f'quantity_{variation.id}']

@register.filter
def get_custom_price_toggle(form, variation):
    """Get the custom price toggle for a specific variation"""
    return form[f'use_custom_price_{variation.id}']

@register.filter
def get_custom_price_field(form, variation):
    """Get the custom price field for a specific variation"""
    return form[f'custom_price_{variation.id}']
