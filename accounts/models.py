    # accounts/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

# accounts/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Business(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120)  # unique эмас — скринда кўринмайди

    # vaqt клонкалари
    created_at = models.DateTimeField(auto_now_add=True)  # DB'да default now() AT TIME ZONE ... бор
    last_seen_at = models.DateTimeField(null=True, blank=True)

    # агент ма'lumotлари
    agent_name = models.CharField(max_length=55, null=True, blank=True)
    agent_promkod = models.TextField(null=True, blank=True)
    link_tg_group = models.URLField(max_length=255, null=True, blank=True)

    # нарх диапазонлари даври (month/year)
    narxlar_diap_davri = models.CharField(max_length=8, null=True, blank=True, db_index=True)

    # ҳисоблагичлар
    oy_bosh_sotil_suv_soni = models.IntegerField(null=True, blank=True)
    yil_bosh_sotil_suv_soni = models.IntegerField(null=True, blank=True)

    # сана ва сервис қоидалари
    sana = models.DateField(default=timezone.localdate, editable=False)
    service_price_rules = models.JSONField(null=True, blank=True)

    # манзил ва TG
    shaxar = models.TextField(null=True, blank=True)
    tg_token = models.TextField(null=True, blank=True)          # unique эмас — скринда кўринмайди
    tuman = models.TextField(null=True, blank=True)
    viloyat = models.TextField(null=True, blank=True)

    # хавфсизлик/аутентификация
    # (скринда password varchar(255), pin_code varchar(10))
    password = models.CharField(max_length=255, null=True, blank=True)
    pin_code = models.CharField(max_length=10, null=True, blank=True)

    # тил (скринда varchar(6))
    lang = models.CharField(max_length=6, default="uz", db_index=True)

    # телефон ва reset код майдонлари
    boss_tel_num = models.CharField(max_length=15, null=True, blank=True)
    reset_code = models.CharField(max_length=6, null=True, blank=True)
    reset_code_expires_at = models.DateTimeField(null=True, blank=True)
    reset_code_attempts = models.SmallIntegerField(default=0)

    class Meta:
        managed = False  # мавжуд жадвал билан миграция қилмасдан тўғридан-тўғри ишлаш
        db_table = "accounts_business"
        verbose_name_plural = "Бизнеслар"
        indexes = [
            models.Index(fields=["narxlar_diap_davri"], name="idx_business_diap_davr"),
            models.Index(fields=["lang"], name="idx_business_lang"),
        ]

    def __str__(self):
        return self.name

    # JSON ни қисқа валидация қилиш (ихтиёрий, ўзингиз қўшган қоида сақланди)
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
            if mn < 0:
                raise ValidationError("min манфий бўлмайди.")
            if mx is not None and mx < mn:
                raise ValidationError("max >= min бўлсин.")
            if price <= 0:
                raise ValidationError("price мусбат бўлсин.")
            segs.append((mn, mx))
        segs.sort(key=lambda x: x[0])
        for i in range(1, len(segs)):
            pmin, pmax = segs[i - 1]
            cmin, _ = segs[i]
            if pmax is None or pmax >= cmin:
                raise ValidationError("Нарх диапазонлари ўзаро тўқнашди.")


class User(AbstractUser):
    ROLE_CHOICES = (("BOSS","Boss"), ("COURIER","Courier"))
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True, null=True)
    business = models.ForeignKey(Business, on_delete=models.PROTECT, null=True, blank=True)


User = get_user_model()

class UserMenedjer(models.Model):
    """
    public.user_menedjer жадвали.
    """
    id   = models.BigAutoField(primary_key=True)          # bigserial
    sana = models.DateField()                             # date

    # 👇 қайта номланган устунлар
    menedjer_id   = models.BigIntegerField(unique=True)   # int8, уникал (эски boss_id)
    menedjer_name = models.CharField(max_length=55)       # varchar(55) (эски boss_name)

    # (бўшлаб қўямиз — аввалги моделингизда бор эди; хоҳласангиз кейин олиб ташлаймиз)
    boss_tel_num = models.CharField(max_length=20, unique=True, blank=True, null=True)

    # Парол/ПИН (ихтиёрий)
    password = models.CharField(max_length=128, blank=True, null=True)
    pin_code = models.CharField(max_length=8,   blank=True, null=True)

    # Интерфейс тили
    lang = models.TextField(blank=True, null=True)

    # Яратилиш вақти
    grated = models.DateTimeField(auto_now_add=True)

    # 🔗 Бир бизнесга бир нечта менежер
    business = models.ForeignKey(
        "Business",
        on_delete=models.PROTECT,
        related_name="menedjer_users",
        null=True, blank=True
    )

    # (ихтиёрий) Django User билан боғлаш
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="menedjer_profile"
    )

    class Meta:
        db_table = "user_menedjer"            # ← жадвал номи
        verbose_name = "Menedjer"
        verbose_name_plural = "Menedjerlar"
        indexes = [
            models.Index(fields=["menedjer_id"], name="idx_usermenedjer_menedjerid"),
        ]

    def __str__(self):
        return f"{self.menedjer_name} ({self.menedjer_id})"
    

class GeoList(models.Model):
    """
    public.geo_list
    """
    viloyat = models.CharField(max_length=80, db_index=True)
    shaxar_yoki_tuman_nomi = models.CharField(max_length=120, db_index=True)
    SHAXAR_YOKI_TUMAN_CHOICES = (("шаҳар", "шаҳар"), ("туман", "туман"))
    shaxar_yoki_tuman = models.CharField(max_length=10, choices=SHAXAR_YOKI_TUMAN_CHOICES, db_index=True)

    class Meta:
        db_table = "geo_list"  # public.geo_list
        verbose_name = "Гео (шаҳар/туман)"
        verbose_name_plural = "Гео (шаҳар/туман)"
        indexes = [
            models.Index(
                fields=["viloyat", "shaxar_yoki_tuman", "shaxar_yoki_tuman_nomi"],
                name="idx_geo_vil_tur_nomi",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["viloyat", "shaxar_yoki_tuman_nomi", "shaxar_yoki_tuman"],
                name="uq_geo_viloyat_nomi_turi",
            )
        ]

    def __str__(self):
        return f"{self.viloyat} — {self.shaxar_yoki_tuman_nomi} ({self.shaxar_yoki_tuman})"


METHOD_CHOICES = [("GET","GET"), ("POST","POST"), ("PUT","PUT"), ("PATCH","PATCH"), ("DELETE","DELETE")]
ACTION_CHOICES = [
    ("Кириш муваффақиятли",  "Кириш муваффақиятли"),
    ("login_fail",     "Кириш муваффақиятсиз"),
    ("reg_ok",         "Рўйхатдан ўтди"),
    ("reg_already",    "Аллақачон рўйхатдан ўтган"),
    ("fp_start",       "Паролни тиклаш коди юборилди"),
    ("fp_verify_ok",   "Код тасдиқланди"),
    ("fp_verify_fail", "Код тасдиқланмади"),
]


class AuditLog(models.Model):
    ts          = models.DateTimeField()                          # DB default now()
    actor_id    = models.BigIntegerField(null=True, blank=True, db_index=True)
    action      = models.CharField(max_length=40, db_index=True, choices=ACTION_CHOICES)
    path        = models.TextField(blank=True)
    method      = models.CharField(max_length=8, blank=True, choices=METHOD_CHOICES)
    status      = models.SmallIntegerField(null=True, blank=True)
    ip          = models.GenericIPAddressField(null=True, blank=True)  # PostgreSQL inet
    user_agent  = models.TextField(blank=True)
    object_type = models.CharField(max_length=30, blank=True)
    object_id   = models.BigIntegerField(null=True, blank=True)
    meta        = models.JSONField(null=True, blank=True)              # PostgreSQL jsonb

    class Meta:
        db_table = "audit_log"
        managed = False                     # ❗️жадвални SQL билан яратганимиз учун Django қайта яратмайди
        ordering = ["-ts"]

    def __str__(self):
        return f"[{self.ts:%Y-%m-%d %H:%M:%S}] {self.action} actor={self.actor_id} obj={self.object_type}:{self.object_id}"

    @property
    def path_short(self):
        return (self.path or "")[:80]
