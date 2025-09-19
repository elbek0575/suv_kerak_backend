from django.contrib import admin
from .models import Buyurtma

@admin.register(Buyurtma)
class BuyurtmaAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "vaqt", "client_tel_num", "suv_soni",
                    "buyurtma_statusi", "pay_status", "kuryer_name",
                    "amount", "grated")
    list_filter = ("buyurtma_statusi", "pay_status", "sana")
    search_fields = ("client_tel_num", "manzil", "kuryer_name")
