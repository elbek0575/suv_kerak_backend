from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.auth import get_user_model

class Business(models.Model):
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class User(AbstractUser):
    ROLE_CHOICES = (("BOSS","Boss"), ("COURIER","Courier"))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True, null=True)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, null=True, blank=True)


User = get_user_model()

class UserBoss(models.Model):
    """
    public.user_boss жадвалига мос келади.
    Эслатма: биометрик 'bio_data' базага сақланмайди (махфийлик/қонун талаблари).
    """
    id = models.BigAutoField(primary_key=True)  # bigserial
    sana = models.DateField()                   # date

    # Telegram идентификатор (масалан, BOSS Telegram ID)
    boss_id = models.BigIntegerField(unique=True)            # int8, уникал
    boss_name = models.CharField(max_length=55)              # varchar(55)
    boss_tel_num = models.CharField(max_length=20, unique=True, blank=True, null=True)

    # Бот токени ва гуруҳ ҳаволаси
    tg_token = models.TextField(unique=True)                 # text, уникал (токен ҳимоя қилинсин)
    link_tg_group = models.URLField(max_length=255, blank=True, null=True, unique=True)

    # Манзил қисмлари
    viloyat = models.TextField(blank=True, null=True)
    shahar = models.TextField(blank=True, null=True)
    tuman = models.TextField(blank=True, null=True)

    # Парол/пин (ихтиёрий)
    password = models.CharField(max_length=128, blank=True, null=True)
    pin_code = models.CharField(max_length=8, blank=True, null=True)

    # ✅ ЯНГИЛАНГАН: агент промо-коди (эски 'promkod' ўрнида)
    agent_promkod = models.TextField(blank=True, null=True)

    # Курьерлар рўйхати (json)
    kuryer_id = models.JSONField(default=dict)

    # Яратилиш вақтини сақлаш
    grated = models.DateTimeField(auto_now_add=True)

    # ✅ ЯНГИ: агент исми ва интерфейс тили
    agent_name = models.CharField(max_length=55, blank=True, null=True)
    lang = models.TextField(blank=True, null=True)

    # (ихтиёрий) Django User билан боғлаш
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="boss_profile")

    class Meta:
        db_table = "user_boss"
        verbose_name = "Boss"
        verbose_name_plural = "Босс турдаги фойдаланувчилар"
        indexes = [
            models.Index(fields=["boss_id"], name="idx_userboss_bossid"),
        ]

    def __str__(self):
        return f"{self.boss_name} ({self.boss_id})"
