# accounts/urls.py
from django.urls import path
from .views import boss_login
from bots.suv_kerak_bot import (register_boss, forgot_boss_password_start, 
                    forgot_boss_password_verify, aiogram_webhook_view
)

urlpatterns = [
    path("boss/register/", register_boss),                 # JSON/Form
    path("boss/register/<path:payload>/", register_boss),  # tg_id/ФИШ/...    
    path("boss/forgot-password/start/",  forgot_boss_password_start),
    path("boss/forgot-password/verify/", forgot_boss_password_verify),
    path("boss/login/", boss_login, name="boss_login"),
    path("aiogram-bot-webhook/", aiogram_webhook_view, name="aiogram_webhook"),
]
