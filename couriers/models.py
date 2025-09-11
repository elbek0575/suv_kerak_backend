from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Business   # 🔗 Бизнес моделини импорт қиламиз


class Kuryer(models.Model):
    id = models.BigAutoField(primary_key=True)           # bigserial
    sana = models.DateField()                            # date
    kuryer_id = models.BigIntegerField(unique=True)      # int8 UNIQUE
    kuryer_name = models.CharField(max_length=55)        # varchar(55)

    avto_num   = models.TextField(blank=True, null=True)     # text
    avto_marka = models.TextField(blank=True, null=True)     # text
    tel_num    = models.CharField(max_length=20, unique=True)  # varchar(20) UNIQUE

    password = models.CharField(max_length=128, blank=True, null=True)  # varchar(128)
    pin_code = models.CharField(max_length=8,   blank=True, null=True)  # varchar(8)

    grated = models.DateTimeField(auto_now_add=True)     # timestamp
    lang   = models.TextField(blank=True, null=True)     # text: 'uz' | 'ru' | 'en'

    # jsonb
    # Маслаҳатли формат: [{"period":"month","min":0,"max":5000,"price":2000,"currency":"UZS"}, ...]
    service_price_rules = models.JSONField(default=list, blank=True)

    # скринда "?" — бутун сон сифатида оламиз
    yil_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)
    oy_bosh_sotil_suv_soni  = models.PositiveIntegerField(default=0)

    # text: 'month' / 'year'
    DIAP_DAVR_CHOICES = (("month", "month"), ("year", "year"))
    narxlar_diap_davri = models.CharField(max_length=8, choices=DIAP_DAVR_CHOICES, default="month")

    # bigserial -> FK
    business = models.ForeignKey(
        Business, on_delete=models.PROTECT,
        related_name="couriers", null=True, blank=True
    )

    class Meta:
        db_table = "kuryer"
        verbose_name = "Kuryer"
        verbose_name_plural = "Kuryerlar"
        indexes = [
            models.Index(fields=["kuryer_id"],            name="idx_kuryer_id"),
            models.Index(fields=["tel_num"],              name="idx_kuryer_tel"),
            models.Index(fields=["narxlar_diap_davri"],   name="idx_kuryer_diap_davr"),
            models.Index(fields=["business"],             name="idx_kuryer_business"),
        ]

    def __str__(self):
        return f"{self.kuryer_name} ({self.tel_num})"

    # --- Валидация ва ёрдамчи функциялар (қолдирдик) ---
    def clean(self):
        rules = self.service_price_rules or []
        norm = []
        for r in rules:
            if not isinstance(r, dict):
                raise ValidationError("service_price_rules элементлари dict бўлиши керак.")
            period = (r.get("period") or "month").strip()
            mn = int(r.get("min", 0))
            mx = r.get("max", None)
            if mx is not None: mx = int(mx)
            price = int(r.get("price", 0))
            if mn < 0: raise ValidationError("Диапазон min манфий бўлмасин.")
            if mx is not None and mx < mn: raise ValidationError("Диапазон max >= min бўлиши керак.")
            if price <= 0: raise ValidationError("Нарх (price) мусбат бўлиши керак.")
            norm.append({"period": period, "min": mn, "max": mx, "price": price})

        for p in ("month", "year"):
            segs = sorted([(r["min"], r["max"]) for r in norm if r["period"] == p], key=lambda x: x[0])
            for i in range(1, len(segs)):
                prev_min, prev_max = segs[i-1]
                cur_min,  cur_max  = segs[i]
                if prev_max is None or prev_max >= cur_min:
                    raise ValidationError(f"'{p}' диапазонлари ўзаро тўқнашди.")

    def resolve_service_price(self, qty: int, period: str = "month") -> int:
        rules = [r for r in (self.service_price_rules or []) if (r.get("period") or "month") == period]
        rules.sort(key=lambda r: int(r.get("min", 0)))
        for r in rules:
            mn = int(r.get("min", 0)); mx = r.get("max", None)
            mx = int(mx) if mx is not None else None
            if qty >= mn and (mx is None or qty <= mx):
                return int(r.get("price", 0))
        return 0