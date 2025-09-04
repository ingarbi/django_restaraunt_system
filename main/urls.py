from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path("subscription-expired/", views.subscription_expired, name="subscription_expired"),
]