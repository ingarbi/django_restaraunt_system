from django.urls import path
from . import views


urlpatterns = [
    path('create/', views.create_order, name='create_order'),
    path('kitchen/', views.kitchen_orders, name='kitchen_orders'),
    path('complete/<int:order_id>/', views.mark_order_completed, name='mark_order_completed'),
    path('delivere/<int:order_id>/', views.mark_order_delivered, name='mark_order_delivered'),
    path('cancel/<int:order_id>/', views.mark_order_cancelled, name='mark_order_cancelled'),
    path('orders/', views.all_orders, name='all_orders'),
]