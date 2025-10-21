from django.http import HttpResponse
from django.template import Template, Context
from django.template.loader import get_template

def test_template_tag(request):
    # Test if the template tag is working
    template = Template('''
        {% load order_filters %}
        {{ fees|sum_fees }}
    ''')
    
    context = Context({
        'fees': [{'amount': 10}, {'amount': 20}]
    })
    
    return HttpResponse(template.render(context))
