# accounts/urls.py
from django.urls import path
from .views import register_boss, telegram_webhook, forgot_boss_password_start, forgot_boss_password_verify, boss_login

urlpatterns = [
    path("boss/register/", register_boss),                 # JSON/Form
    path("boss/register/<path:payload>/", register_boss),  # tg_id/ФИШ/...
    path("webhook/", telegram_webhook),
    path("boss/forgot-password/start",  forgot_boss_password_start),
    path("boss/forgot-password/verify", forgot_boss_password_verify),
    path("boss/login", boss_login, name="boss_login"),
]
