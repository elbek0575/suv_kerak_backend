from django.contrib import admin
from .models import AgentAccount

@admin.register(AgentAccount)
class AgentAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "sana", "agent_name", "agent_id", "status", "lang", "grated")
    search_fields = ("agent_name", "agent_id", "boss_name")
    list_filter = ("status", "sana")
