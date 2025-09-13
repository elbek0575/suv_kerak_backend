# accounts/urls.py
from django.urls import path
from .views import register_boss, telegram_webhook, forgot_boss_password

urlpatterns = [
    path("boss/register/", register_boss),                 # JSON/Form
    path("boss/register/<path:payload>/", register_boss),  # tg_id/ФИШ/...
    path("webhook/", telegram_webhook),
    path("boss/forgot-password/", forgot_boss_password),
]
