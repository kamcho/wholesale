from django.core.management.base import BaseCommand
from django.template import engines

class Command(BaseCommand):
    help = 'Check if template tags are properly registered'

    def handle(self, *args, **options):
        # Get the default template engine
        engine = engines['django']
        
        # Try to get the template tag library
        try:
            lib = engine.engine.template_libraries.get('order_filters')
            if lib:
                self.stdout.write(self.style.SUCCESS('order_filters template tag library is properly registered!'))
                self.stdout.write(f'Available filters: {list(lib.filters.keys())}')
            else:
                self.stdout.write(self.style.ERROR('order_filters template tag library is not registered!'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error checking template tags: {str(e)}'))
