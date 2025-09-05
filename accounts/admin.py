# accounts/admin.py
from django.contrib import admin
from .models import UserBoss, Business

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display  = ("id","name","narxlar_diap_davri","yil_bosh_sotil_suv_soni","oy_bosh_sotil_suv_soni","grated")
    search_fields = ("name",)
    list_filter   = ("narxlar_diap_davri",)

@admin.register(UserBoss)
class UserBossAdmin(admin.ModelAdmin):
    # ↓ Modelda mavjud ustunlar bilan ishlaymiz
    list_display  = ("id", "boss_name", "boss_tel_num", "boss_id", "business", "grated")
    search_fields = ("boss_name", "boss_tel_num", "boss_id")
    list_filter   = ("business", "sana")

