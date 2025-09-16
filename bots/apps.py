# bots/apps.py
from django.apps import AppConfig
import asyncio
import threading


class BotsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bots"

    def ready(self):
        # ❌ Hech qanday thread yoki asyncio.run() boshlamang.
        # Webhook orqali ishlaymiz; dp.feed_update() ni view ichida chaqiramiz.
        pass

