from django.db import models
from django.urls import reverse
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name
    
    
class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    category = models.ForeignKey(
        Category,
        related_name="menu_items",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Меню'
        verbose_name_plural = 'Меню'

class Order(models.Model):

    STATUS_CHOICES = (
        ("cancelled", "Отменен"),
        ("pending", "В ожидании"),
        ("done", "Готов"),
        ("delivered", "Доставлен"),
    )
    ORDER_TYPE_CHOICES = [
        ("dine_in", "В зале"),
        ("takeaway", "На вынос"),
        ("delivery", "Доставка"),
    ]

    order_number = models.CharField(verbose_name="№ Заказа", max_length=10, unique=True, editable=False)
    created_at = models.DateTimeField(verbose_name="Дата", auto_now_add=True)
    status = models.CharField(verbose_name="Статус", max_length=10, choices=STATUS_CHOICES, default="pending")
    order_type = models.CharField(verbose_name="Тип", 
        max_length=10,
        choices=ORDER_TYPE_CHOICES,
        default="dine_in",
        blank=True,
        null=True,
    )
    
    phone_number = models.CharField(verbose_name="Телефон", max_length=15, null=True, blank=True)  # Unique phone number
    name = models.CharField(verbose_name="Имя", max_length=100, null=True, blank=True)  # Optional name
    address = models.CharField(verbose_name="Адрес", max_length=300,null=True, blank=True)  # Optional address
    total_sum = models.PositiveSmallIntegerField(verbose_name="Итого", default=0)
    def __str__(self):
        return f"Order {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Generate order number with date prefix (e.g., "2023-10-05-001")
            today = timezone.now().date()
            date_prefix = today.strftime("%Y-%m-%d")
            last_order = (
                Order.objects.filter(order_number__startswith=date_prefix)
                .order_by("order_number")
                .last()
            )
            if last_order:
                last_number = int(last_order.order_number.split("-")[-1])
                self.order_number = f"{date_prefix}-{last_number + 1:03d}"  # Increment and format as 001, 002, etc.
            else:
                self.order_number = f"{date_prefix}-001"  # First order of the day
        super().save(*args, **kwargs)

    def get_human_readable_order_number(self):
        return self.order_number.split("-")[-1]
    
    def get_absolute_url(self):
        return reverse('order_detail', kwargs={'order_id': self.id})

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} для заказа - {self.order.order_number}"

    class Meta:
        verbose_name = 'Список заказанных блюд'
        verbose_name_plural = 'Список заказанных блюд'