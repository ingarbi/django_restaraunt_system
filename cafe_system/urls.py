from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from custom_auth import urls
from custom_auth.views import*

urlpatterns = [
    path('admin/', admin.site.urls),
    path('orders/', include('orders.urls')),
    path("", include('main.urls')),
    path("auth/", include('custom_auth.urls')),
     path('login/', loginView, name='login'),
    path('logout/', logoutView, name='logout'),
    path('register/', registerView, name='register'),
]