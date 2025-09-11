# accounts/admin.py
from django.contrib import admin
from .models import UserMenedjer, Business

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display  = ("id","name","narxlar_diap_davri","yil_bosh_sotil_suv_soni","oy_bosh_sotil_suv_soni","grated")
    search_fields = ("name",)
    list_filter   = ("narxlar_diap_davri",)

@admin.register(UserMenedjer)
class UserMenedjerAdmin(admin.ModelAdmin):
    # ↓ Modelda mavjud ustunlar bilan ishlaymiz
    list_display  = ("id", "sana", "menedjer_name", "menedjer_id", "grated")
    search_fields = ("menedjer_name", "menedjer_id")
    list_filter   = ("business", "sana")

