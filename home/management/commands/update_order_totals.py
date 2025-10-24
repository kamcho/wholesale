from django.core.management.base import BaseCommand
from home.models import Order

class Command(BaseCommand):
    help = 'Update the total field for all orders by recalculating from order items'

    def handle(self, *args, **options):
        orders = Order.objects.all()
        total_orders = orders.count()
        updated = 0
        
        self.stdout.write(f'Found {total_orders} orders to update...')
        
        for order in orders:
            old_total = order.total
            order.total = order.get_total_cost()
            
            if order.total != old_total:
                order.save(skip_total_update=True)  # Skip the total update to prevent recursion
                updated += 1
                self.stdout.write(f'Updated order #{order.id}: {old_total} -> {order.total}')
        
        self.stdout.write(self.style.SUCCESS(f'Successfully updated totals for {updated} out of {total_orders} orders'))
