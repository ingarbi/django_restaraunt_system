from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders'

    def ready(self, *args, **kwargs):
        from django.db.models.signals import post_save
        from orders.signals import new_order
        
        my_model = self.get_model('Order')
        post_save.connect(new_order, sender=my_model)
