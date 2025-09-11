# couriers/admin.py
from django.contrib import admin
from .models import Kuryer

@admin.register(Kuryer)
class KuryerAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sana", "kuryer_name", "tel_num",
        "avto_num", "avto_marka",
        "narxlar_diap_davri", "rules_cnt",
        "yil_bosh_sotil_suv_soni", "oy_bosh_sotil_suv_soni",
        "grated",
    )
    search_fields = ("kuryer_name", "tel_num", "=kuryer_id")
    list_filter = ("sana", "avto_marka", "narxlar_diap_davri")
    readonly_fields = ()

    def rules_cnt(self, obj):
        try:
            return len(obj.service_price_rules or [])
        except Exception:
            return 0
    rules_cnt.short_description = "Тариф қоидалари"

