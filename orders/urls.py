from django.urls import path

from . import views

urlpatterns = [
    path("create/", views.create_order, name="create_order"),
    path("kitchen/", views.kitchen_orders, name="kitchen_orders"),
    path(
        "complete/<int:order_id>/",
        views.mark_order_completed,
        name="mark_order_completed",
    ),
    path(
        "delivere/<int:order_id>/",
        views.mark_order_delivered,
        name="mark_order_delivered",
    ),
    path(
        "cancel/<int:order_id>/",
        views.mark_order_cancelled,
        name="mark_order_cancelled",
    ),
    path("order/<int:order_id>/pdf/", views.order_pdf, name="order_pdf"),
    path(
        "order_quick/<int:order_id>/pdf/",
        views.quick_receipt_printing,
        name="quick_receipt_printing",
    ),
    path("order/<int:order_id>/", views.order_detail, name="order_detail"),
    path("orders/", views.all_orders, name="all_orders"),
]
