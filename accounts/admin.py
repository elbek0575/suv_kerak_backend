# accounts/admin.py
from django.contrib import admin
from .models import UserMenedjer, Business, GeoList, AuditLog

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display  = ("id","name","narxlar_diap_davri","yil_bosh_sotil_suv_soni","oy_bosh_sotil_suv_soni","created_at")
    search_fields = ("name",)
    list_filter   = ("narxlar_diap_davri",)

@admin.register(UserMenedjer)
class UserMenedjerAdmin(admin.ModelAdmin):
    # ↓ Modelda mavjud ustunlar bilan ishlaymiz
    list_display  = ("id", "sana", "menedjer_name", "menedjer_id", "grated")
    search_fields = ("menedjer_name", "menedjer_id")
    list_filter   = ("business", "sana")
    

@admin.register(GeoList)
class GeoListAdmin(admin.ModelAdmin):
    list_display  = ("id", "viloyat", "shaxar_yoki_tuman_nomi", "shaxar_yoki_tuman")
    list_filter   = ("viloyat", "shaxar_yoki_tuman")
    search_fields = ("viloyat", "shaxar_yoki_tuman_nomi")
    ordering      = ("viloyat", "shaxar_yoki_tuman", "shaxar_yoki_tuman_nomi")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display  = ("id", "ts", "action", "actor_id", "object_type", "object_id", "status", "method", "ip", "path_short")
    list_filter   = ("action", "method", "status", "object_type")
    search_fields = ("path", "user_agent", "meta")  # рақамли майдонлар б-н search қилиш шарт эмас
    date_hierarchy = "ts"
    ordering      = ("-ts",)

    readonly_fields = ("ts","actor_id","action","path","method","status","ip","user_agent","object_type","object_id","meta_pretty")
    fieldsets = (
        (None, {"fields": ("ts","action","actor_id","object_type","object_id","status","method")}),
        ("Request", {"fields": ("path","ip","user_agent")}),
        ("Meta (JSON)", {"fields": ("meta_pretty",)}),
    )

    def meta_pretty(self, obj):
        try:
            return json.dumps(obj.meta, ensure_ascii=False, indent=2, sort_keys=True)
        except Exception:
            return str(obj.meta)
    meta_pretty.short_description = "meta"

    # Audit’ни админдан қўл билан ўзгартирмаслик қулай
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False