from django.contrib import admin
from .models import UserBoss

@admin.register(UserBoss)
class UserBossAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "boss_name", "boss_id", "viloyat", "shahar", "tuman", "grated")
    search_fields = ("boss_name", "boss_id", "tg_token")
    list_filter = ("viloyat", "shahar", "tuman")

