# finance/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import CashMenedjer, CashState, CourierWaterBottleBalance, BusinessSystemAccount, CashKuryer

@admin.register(CashMenedjer)
class CashMenedjerAdmin(admin.ModelAdmin):
    list_display  = ("id", "sana", "vaqt", "menedjer_name", "kuryer_name",
                     "cash_operation", "income", "expense", "balance", "grated")
    list_filter   = ("cash_operation", "sana")
    search_fields = ("menedjer_name", "kuryer_name", "client_tel_num")
    readonly_fields = ("cash_message",)  # автоматик тўлади

@admin.register(CashState)
class CashStateAdmin(admin.ModelAdmin):
    list_display  = ("id", "sana", "menedjer_name", "kuryer_name",
                     "cash_operation", "status", "income", "expense", "balance", "grated")
    list_filter   = ("status", "cash_operation", "sana")
    search_fields = ("menedjer_name", "menedjer_id", "kuryer_name")
            
@admin.register(CourierWaterBottleBalance)
class CourierWaterBottleBalanceAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sana", "vaqt", "business", "kuryer_name",
        "operation", "income", "expense",
        "water_balance", "bottle_balance",
        "status", "grated",
    )
    list_filter  = ("business", "operation", "status", "sana")
    search_fields = ("kuryer_name", "kuryer_id", "client_tel_num", "boss_name")
    readonly_fields = ("water_balance", "bottle_balance", "grated")
    
@admin.register(BusinessSystemAccount)
class BusinessSystemAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sana", "vaqt", "business",
        "menedjer_name", "kuryer_name",
        "tulov_tizimi", "operation",
        "income", "expense", "tizimdagi_balance",
        "status", "grated",
    )
    list_filter   = ("business", "operation", "status", "sana")
    search_fields = ("business__name", "menedjer_name", "kuryer_name", "buyurtma_num")
    date_hierarchy = "sana"
    ordering = ("-grated",)
    readonly_fields = ("tizimdagi_balance", "grated")

    fieldsets = (
        ("Вақт ва тадбиркор", {
            "fields": ("business", "sana", "vaqt")
        }),
        ("Менежер / Курер / Клиент", {
            "fields": ("menedjer_id","menedjer_name","kuryer_id","kuryer_name","client_tg_id","buyurtma_num")
        }),
        ("Операция ва тўлов", {
            "fields": ("tulov_tizimi","operation","income","expense","status")
        }),
        ("Қолдиқ", {
            "fields": ("tizimdagi_balance","grated")
        }),
    )

@admin.register(CashKuryer)
class CashKuryerAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "vaqt", "kuryer_name",
                    "cash_operation", "income", "expense",
                    "balance", "status", "grated")
    list_filter = ("status", "cash_operation", "sana")
    search_fields = ("kuryer_name", "kuryer_id", "client_tel_num", "boss_name")
    readonly_fields = ("balance",)

