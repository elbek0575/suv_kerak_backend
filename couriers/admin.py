from django.contrib import admin
from .models import Kuryer

@admin.register(Kuryer)
class KuryerAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "kuryer_name", "tel_num", "avto_num", "avto_marka", "grated")
    search_fields = ("kuryer_name", "tel_num", "kuryer_id")
    list_filter = ("sana", "avto_marka")
