from django.db import models
from accounts.models import Business
from couriers.models import Kuryer

class Buyurtma(models.Model):
    business = models.ForeignKey(Business, on_delete=models.PROTECT)

    sana = models.DateField()
    vaqt = models.TimeField()

    client_tg_id = models.BigIntegerField(null=True, blank=True)
    client_tel_num = models.CharField(max_length=15)

    suv_soni = models.PositiveIntegerField()
    manzil = models.TextField()

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
        ("cash", "Нақд"),
        ("online", "Онлайн"),
    )
    pay_status = models.CharField(max_length=8, choices=PAY_STATUS, default="none")

    # FK ва снапшотлар
    kuryer = models.ForeignKey(Kuryer, on_delete=models.SET_NULL, null=True, blank=True, related_name="buyurtmalar")
    kuryer_ext_id = models.BigIntegerField(null=True, blank=True)       # ➜ Эски kuryer_id ўрнига тарихий
    kuryer_name = models.CharField(max_length=55, blank=True, null=True)
    kuryer_tel_num = models.CharField(max_length=15, blank=True, null=True)

    sotilgan_tara_soni = models.PositiveIntegerField(default=0)
    yil_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)
    oy_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)

    qullanilgan_akciya = models.TextField(blank=True, null=True)
    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "buyurtmalar"
        verbose_name = "Буюртма"
        verbose_name_plural = "Буюртмалар"
        indexes = [
            models.Index(fields=["business", "sana"], name="idx_buyurtma_biz_sana"),
            models.Index(fields=["business", "buyurtma_statusi"], name="idx_buyurtma_biz_status"),
            models.Index(fields=["business", "client_tel_num"], name="idx_buyurtma_biz_client_tel"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} — {self.client_tel_num} ({self.suv_soni} дона)"
