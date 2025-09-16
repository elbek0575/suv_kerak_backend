# orders/urls.py
from django.urls import path
from .views import main_menu_stats, create_buyurtma

urlpatterns = [
    path("main-menu-stats/", main_menu_stats, name="main_menu_stats"),
    path("create/", create_buyurtma, name="create_buyurtma"),
]
