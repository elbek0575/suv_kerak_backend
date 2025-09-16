# bots/urls.py
from django.urls import path
from .suv_kerak_bot import (
    register_boss,
    forgot_boss_password_start,
    forgot_boss_password_verify,
    aiogram_webhook_view,
)

app_name = "bots"

urlpatterns = [
    path("register/", register_boss, name="register_boss"),
    path("forgot-password/start/",  forgot_boss_password_start,  name="forgot_pwd_start"),
    path("forgot-password/verify/", forgot_boss_password_verify, name="forgot_pwd_verify"),
    path("aiogram-bot-webhook/",   aiogram_webhook_view,         name="aiogram_webhook"),
]
