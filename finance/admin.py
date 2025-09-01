# finance/admin.py
from django.contrib import admin
from .models import CashBoss

@admin.register(CashBoss)
class CashBossAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "vaqt", "boss_name", "kuryer_name",
                    "cash_operation", "income", "expense", "balance", "cash_message", "grated")
    list_filter  = ("cash_operation", "sana")
    search_fields = ("boss_name", "kuryer_name", "client_tel_num")
    readonly_fields = ("cash_message",)  # автоматик тўлади
