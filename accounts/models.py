from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

class Business(models.Model):
    name = models.CharField(max_length=120, unique=True)

    sana          = models.DateField(null=True, blank=True)
    tg_token      = models.TextField(unique=True, null=True, blank=True)             # 🔁 матн (token)
    link_tg_group = models.URLField(max_length=255, unique=True, null=True, blank=True)

    viloyat = models.TextField(null=True, blank=True)
    shaxar  = models.TextField(null=True, blank=True)
    tuman   = models.TextField(null=True, blank=True)

    grated = models.DateTimeField(auto_now_add=True)

    agent_name    = models.CharField(max_length=55, null=True, blank=True)
    agent_promkod = models.TextField(null=True, blank=True)

    # 🧾 Сув нархлари JSON (диапазонлар)
    service_price_rules = models.JSONField(default=list, blank=True)

    DIAP_DAVR = (("month", "month"), ("year", "year"))
    narxlar_diap_davri = models.CharField(max_length=8, choices=DIAP_DAVR, default="month")

    # 📈 ҳисоблагичлар
    yil_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)
    oy_bosh_sotil_suv_soni  = models.PositiveIntegerField(default=0)

    # 🟡 Сариқ устунлар (ихтиёрий, хавфсизлик учун plain пароль сақламаслик керак)
    password = models.CharField(max_length=128, null=True, blank=True)  # ҳеч қачон очиқ парол сақламанг!
    pin_code = models.CharField(max_length=8,   null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounts_business"
        verbose_name_plural = "Бизнеслар"
        indexes = [
            models.Index(fields=["narxlar_diap_davri"], name="idx_business_diap_davr"),
            models.Index(fields=["tg_token"], name="idx_business_tg_token"),
        ]

    def __str__(self):
        return self.name

    # JSON ни қисқа валидация қилиш
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