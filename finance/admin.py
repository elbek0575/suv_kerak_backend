# finance/admin.py
from django.contrib import admin
from django.utils import timezone
from .models import CashBoss, CashState, CourierWaterBottleBalance, BossSystemAccount, CashKuryer

@admin.register(CashBoss)
class CashBossAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "vaqt", "boss_name", "kuryer_name",
                    "cash_operation", "income", "expense", "balance", "cash_message", "grated")
    list_filter  = ("cash_operation", "sana")
    search_fields = ("boss_name", "kuryer_name", "client_tel_num")
    readonly_fields = ("cash_message",)  # автоматик тўлади

@admin.register(CashState)
class CashStateAdmin(admin.ModelAdmin):
    list_display = ("sana","vaqt","boss_name","kuryer_name","cash_operation","income","expense","status")
    list_filter = ("status","cash_operation","sana","business")
    actions = ["approve_selected","reject_selected"]

    @admin.action(description="✅ Approve selected")
    def approve_selected(self, request, queryset):
        now_dt = timezone.now()
        for obj in queryset.select_for_update():
            obj.approve(now_dt)

    @admin.action(description="❌ Reject selected")
    def reject_selected(self, request, queryset):
        now_dt = timezone.now()
        for obj in queryset:
            obj.reject(now_dt)
            
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
    
@admin.register(BossSystemAccount)
class BossSystemAccountAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sana", "vaqt", "business", "operation",
        "income", "expense", "balance", "note", "grated",
    )
    list_filter = ("business", "operation", "sana")
    search_fields = ("business__name",)
    date_hierarchy = "sana"
    ordering = ("-grated",)

    readonly_fields = ("balance", "grated")  # баланс авт. ҳисобланади
    fieldsets = (
        ("Вақт ва тадбиркор", {
            "fields": ("business", "sana", "vaqt")
        }),
        ("Операция", {
            "fields": ("operation", "income", "expense", "note")
        }),
        ("Қолдиқ", {
            "fields": ("balance", "grated")
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
