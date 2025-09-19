# orders/models.py
from django.db import models
from accounts.models import Business
from couriers.models import Kuryer
from django.core.validators import MinValueValidator, MaxValueValidator

class Buyurtma(models.Model):
    business = models.ForeignKey(Business, on_delete=models.PROTECT)

    sana = models.DateField()
    vaqt = models.TimeField()

    client_tg_id = models.BigIntegerField(null=True, blank=True)
    client_tel_num = models.CharField(max_length=15)

    suv_soni = models.PositiveIntegerField()
    manzil = models.TextField()
    manzil_izoh = models.TextField(blank=True, null=True,
                                   help_text="Буюртмачи хонадонини топиш учун қисқа изоҳ")

    ORDER_STATUS = (
        ("pending", "Кутилмоқда"),
        ("assigned", "Бириктирилди"),
        ("accepted", "Қабул қилинди"),
        ("on_way", "Йўлда"),
        ("delivered", "Топширилди"),
        ("failed", "Бажарилмади"),
        ("cancelled", "Бекор қилинди"),
    )
    buyurtma_statusi = models.CharField(max_length=12, choices=ORDER_STATUS, default="pending")

    PAY_STATUS = (
        ("none", "Йўқ"),
        ("waiting_for_payment", "Онлайн тўлаш кутилмоқда"),
        ("pending", "Онлайн жараёнда"),        
        ("completed_online", "Онлайн тўланди"),
        ("cash", "Нақд"),
    )
    pay_status = models.CharField(max_length=55, choices=PAY_STATUS, default="none")

    kuryer = models.ForeignKey(Kuryer, on_delete=models.SET_NULL, null=True, blank=True, related_name="buyurtmalar")
    kuryer_name = models.CharField(max_length=55, blank=True, null=True)
    kuryer_tel_num = models.CharField(max_length=15, blank=True, null=True)

    sotilgan_tara_soni = models.PositiveIntegerField(default=0)
    yil_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)
    oy_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)

    # 🆕 order_num — “02-02-02” формати каби
    order_num = models.CharField(max_length=32, unique=True, db_index=True, blank=True, null=True)

    grated = models.DateTimeField(auto_now_add=True)

    lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                              validators=[MinValueValidator(-90), MaxValueValidator(90)])
    lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True,
                              validators=[MinValueValidator(-180), MaxValueValidator(180)])
    location_accuracy = models.PositiveIntegerField(null=True, blank=True,
                                                    validators=[MaxValueValidator(5000)])
    LOCATION_SOURCES = (("tg", "telegram"), ("geocode", "geocode"), ("manual", "manual"))
    location_source = models.CharField(max_length=16, choices=LOCATION_SOURCES, default="manual")
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # 💧 Сув суммаси
    class Meta:
        db_table = "buyurtmalar"
        verbose_name = "Буюртма"
        verbose_name_plural = "Буюртмалар"
        indexes = [
            models.Index(fields=["business", "sana"], name="idx_buyurtma_biz_sana"),
            models.Index(fields=["business", "buyurtma_statusi"], name="idx_buyurtma_biz_status"),
            models.Index(fields=["business", "client_tel_num"], name="idx_buyurtma_biz_client_tel"),
        ]

    def save(self, *args, **kwargs):
        self.manzil_izoh = (self.manzil_izoh or "").strip() or None
        super().save(*args, **kwargs)
