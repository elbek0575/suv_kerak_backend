# accounts/urls.py
from django.urls import re_path, path
from .views import boss_login
from bots.suv_kerak_bot import aiogram_webhook_view

urlpatterns = [       
    re_path(r"^boss/login/?$", boss_login, name="boss_login"),    
]
