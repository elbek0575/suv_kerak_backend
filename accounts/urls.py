# accounts/urls.py
from django.urls import re_path
from .views import boss_login

urlpatterns = [       
    re_path(r"^boss/login/?$", boss_login, name="boss_login"),   
]
