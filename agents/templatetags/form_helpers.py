from django import template

register = template.Library()

@register.filter(name='widget_type')
def widget_type(field):
    """
    Template filter to get the widget type of a form field
    """
    if hasattr(field, 'field') and hasattr(field.field, 'widget'):
        return field.field.widget.__class__.__name__.lower()
    return ''

@register.filter(name='is_checkbox')
def is_checkbox(field):
    """
    Check if a field is a checkbox
    """
    return field.field.widget.input_type == 'checkbox' if hasattr(field.field.widget, 'input_type') else False

@register.filter(name='is_textarea')
def is_textarea(field):
    """
    Check if a field is a textarea
    """
    return field.field.widget.__class__.__name__.lower() == 'textarea'

@register.filter(name='is_select')
def is_select(field):
    """
    Check if a field is a select
    """
    return field.field.widget.__class__.__name__.lower() in ['select', 'selectmultiple', 'select2widget', 'select2multiplewidget']
