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
    link_tg_group = models.URLField(max_length=255, blank=True, null=True, unique=True)  # ? → URL; ихтиёрий

    # Манзил қисмлари
    viloyat = models.TextField(blank=True, null=True)
    shahar = models.TextField(blank=True, null=True)
    tuman = models.TextField(blank=True, null=True)

    # Парол/пин ҳақида: тавсия — ДЖАНГО User паролини ишлатиш; шу иккиси ихтиёрий қўйилди
    password = models.CharField(max_length=128, blank=True, null=True)  # агар керак бўлса, бу ерга ҲЕЧ ҚАЧОН очиқ парол сақланмасин!
    pin_code = models.CharField(max_length=8, blank=True, null=True)    # varchar(8)

    # Промо-код (ихтиёрий)
    promkod = models.TextField(blank=True, null=True)

    # Курьерлар рўйхати/маппинги (json)
    # Масалан: {"active":[123456789, 987654321], "blocked":[111222333]}
    kuryer_id = models.JSONField(default=dict)  # json{}

    # Яратилиш вақтини сақлаш
    grated = models.DateTimeField(auto_now_add=True)  # timestamp

    # (ихтиёрий) Агар Django User билан боғлашни истасангиз:
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="boss_profile")

    class Meta:
        db_table = "user_boss"   # PostgreSQL'да default schema 'public', шунинг учун тўлиқ 'public.user_boss' шарт эмас
        verbose_name = "Boss"
        verbose_name_plural = "Босс турдаги фойдаланувчилар"
        indexes = [
            models.Index(fields=["boss_id"], name="idx_userboss_bossid"),
        ]

    def __str__(self):
        return f"{self.boss_name} ({self.boss_id})"

