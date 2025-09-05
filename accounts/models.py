from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

class Business(models.Model):
    name = models.CharField(max_length=120, unique=True)

    # 🟡 Скриндаги янги устунлар
    sana          = models.DateField(null=True, blank=True)  # date
    tg_token      = models.BigIntegerField(unique=True, null=True, blank=True)
    link_tg_group = models.BigIntegerField(unique=True, null=True, blank=True)

    viloyat = models.TextField(null=True, blank=True)
    shaxar  = models.TextField(null=True, blank=True)
    tuman   = models.TextField(null=True, blank=True)

    grated = models.DateTimeField(auto_now_add=True)  # time_stamp

    agent_name    = models.CharField(max_length=55, null=True, blank=True)
    agent_promkod = models.TextField(null=True, blank=True)

    # Сув нархлари (фаол диапазонлар) — JSONB
    # [{"min":0,"max":100,"price":10000,"currency":"UZS"}, ...]
    service_price_rules = models.JSONField(default=list, blank=True)

    # Диапазонлар қўлланадиган давр: month/year
    DIAP_DAVR = (("month", "month"), ("year", "year"))
    narxlar_diap_davri = models.CharField(max_length=8, choices=DIAP_DAVR, default="month")

    # “?” устунлар — ҳисоблагичлар (ҳамёнбоп тип: PositiveInteger)
    yil_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)
    oy_bosh_sotil_suv_soni  = models.PositiveIntegerField(default=0)  
     

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_business"
        verbose_name_plural = "Бизнесс эгаси турдаги фойдаланувчилар"
        indexes = [
            models.Index(fields=["narxlar_diap_davri"], name="idx_business_diap_davr"),
        ]

    def __str__(self): 
        return self.name

    # Ихтиёрий: JSON валидацияси (қисқа)
    def clean(self):
        rules = self.service_price_rules or []
        segs = []
        for r in rules:
            if not isinstance(r, dict):
                raise ValidationError("service_price_rules элементлари dict бўлсин.")
            mn = int(r.get("min", 0))
            mx = r.get("max", None)
            if mx is not None:
                mx = int(mx)
            price = int(r.get("price", 0))
            if mn < 0: raise ValidationError("min манфий бўлмайди.")
            if mx is not None and mx < mn: raise ValidationError("max >= min бўлсин.")
            if price <= 0: raise ValidationError("price мусбат бўлсин.")
            segs.append((mn, mx))
        segs.sort(key=lambda x: x[0])
        for i in range(1, len(segs)):
            pmin, pmax = segs[i-1]
            cmin, _    = segs[i]
            if pmax is None or pmax >= cmin:
                raise ValidationError("Нарх диапазонлари ўзаро тўқнашди.")

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
    boss_id = models.BigIntegerField(unique=True)         # int8, уникал
    boss_name = models.CharField(max_length=55)           # varchar(55)
    boss_tel_num = models.CharField(max_length=20, unique=True, blank=True, null=True)

    # ✅ Ортиқча майдонлар олиб ташланди (улар Business'да сақланади):
    # tg_token, link_tg_group, viloyat, shahar, tuman,
    # agent_promkod, kuryer_id, agent_name

    # Парол/пин (ихтиёрий)
    password = models.CharField(max_length=128, blank=True, null=True)  # парол (hashed бўлиши керак)
    pin_code = models.CharField(max_length=8,   blank=True, null=True)  # пин код

    # Интерфейс тили
    lang = models.TextField(blank=True, null=True)

    # Яратилиш вақтини сақлаш
    grated = models.DateTimeField(auto_now_add=True)  # timestamp

    # 🔗 Бир бизнесга кўп босс
    business = models.ForeignKey(
        "Business",
        on_delete=models.PROTECT,
        related_name="boss_users",
        null=True, blank=True
    )

    # (ихтиёрий) Django User билан боғлаш
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="boss_profile"
    )

    class Meta:
        db_table = "user_boss"
        verbose_name = "Boss"
        verbose_name_plural = "Босс турдаги фойдаланувчилар"
        indexes = [
            models.Index(fields=["boss_id"], name="idx_userboss_bossid"),
        ]

    def __str__(self):
        return f"{self.boss_name} ({self.boss_id})"
