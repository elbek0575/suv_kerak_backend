from django.db import models
from accounts.models import Business  # мавжуд бизнес моделига боғлаймиз

class AgentAccount(models.Model):
    id = models.BigAutoField(primary_key=True)
    sana = models.DateField()
    agent_id = models.BigIntegerField(unique=True)       # ташқи ID (масалан, Telegram ID)
    agent_name = models.CharField(max_length=55)
    agent_promkod = models.TextField(blank=True, null=True)

    # агент қайси бизнес(лар)га боғланганини сақлаш
    business_map = models.JSONField(default=list, blank=True)
    business = models.ForeignKey(
        Business, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="agents"
    )

    business_name = models.CharField(max_length=55, blank=True, null=True)
    status = models.TextField(blank=True, null=True)     # active / blocked
    lang = models.TextField(blank=True, null=True)       # uz / ru / en

    # 🟡 Сариқ устунлар
    password = models.CharField(max_length=128, blank=True, null=True)  # hashed пароль, очиқ сақламаслик керак
    pin_code = models.CharField(max_length=8, blank=True, null=True)

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agent_account"
        verbose_name = "Сотув агенти"
        verbose_name_plural = "Сотув агентлари"
        indexes = [
            models.Index(fields=["agent_id"], name="idx_agent_agent_id"),
            models.Index(fields=["status"], name="idx_agent_status"),
        ]

    def __str__(self):
        return f"{self.agent_name} (#{self.agent_id})"


