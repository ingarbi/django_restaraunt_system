from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    USER_ROLE_CHOICES = (
        ('cashier', 'Кассир'),
        ('cook', 'Повар'),
        ('supervisor', 'Супервайзер'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=11, choices=USER_ROLE_CHOICES)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
    
    class Meta:
        verbose_name = 'Аккаунт'
        verbose_name_plural = 'Аккаунты'