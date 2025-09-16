# accounts/urls.py
from django.urls import path
from .views import boss_login

urlpatterns = [       
    path("boss/login/", boss_login, name="boss_login"),
    
]
