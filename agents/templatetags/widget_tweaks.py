from django import template
from django.forms import CheckboxInput, FileInput, RadioSelect, CheckboxSelectMultiple

register = template.Library()

@register.filter(name='add_class')
def add_class(field, css):
    """
    Add a CSS class to a form field.
    Usage: {{ field|add_class:"class1 class2" }}
    """
    attrs = {}
    class_old = field.field.widget.attrs.get('class', '')
    attrs['class'] = f"{class_old} {css}".strip()
    
    # Handle special widget types
    if isinstance(field.field.widget, (CheckboxInput, FileInput, RadioSelect, CheckboxSelectMultiple)):
        attrs['class'] = f"{attrs['class']} form-check-input".strip()
    
    return field.as_widget(attrs=attrs)
