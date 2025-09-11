# accounts/urls.py
from django.urls import path
from .views import register_boss, telegram_webhook

urlpatterns = [
    path("boss/register/", register_boss),                 # JSON/Form
    path("boss/register/<path:payload>/", register_boss),  # tg_id/ФИШ/...
    path("webhook/", telegram_webhook),
]
