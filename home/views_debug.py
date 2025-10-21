from django.http import HttpResponse
from django.template import engines

def debug_template_tags(request):
    engine = engines['django'].engine
    
    # Get all registered template tag libraries
    libraries = engine.template_libraries
    
    # Check if our library is registered
    is_registered = 'order_filters' in libraries
    
    # Get list of all available template tags
    available_tags = []
    if is_registered:
        lib = libraries['order_filters']
        available_tags = list(lib.filters.keys())
    
    # Generate response
    response = [
        f"Order Filters Registered: {is_registered}",
        f"Available tags in order_filters: {', '.join(available_tags) if available_tags else 'None'}",
        "\nAll registered template tag libraries:",
        *[f"- {name}: {len(lib.filters)} filters, {len(lib.tags)} tags" 
          for name, lib in libraries.items()]
    ]
    
    return HttpResponse("\n".join(response), content_type="text/plain")
