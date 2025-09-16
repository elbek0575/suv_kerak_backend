# bots/urls.py
from django.urls import re_path
from .suv_kerak_bot import (
    register_boss,
    forgot_boss_password_start,
    forgot_boss_password_verify,
    aiogram_webhook_view,
)

app_name = "bots"

urlpatterns = [
    re_path(r"^boss/register/?$", register_boss, name="register_boss"),
    re_path(r"^boss/forgot-password/start/?$",  forgot_boss_password_start,  name="forgot_pwd_start"),
    re_path(r"^boss/forgot-password/verify/?$", forgot_boss_password_verify, name="forgot_pwd_verify"),
    re_path(r"^aiogram-bot-webhook/?$",        aiogram_webhook_view,        name="aiogram_webhook"),
]
