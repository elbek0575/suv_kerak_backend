from django.db import models
from django.core.exceptions import ValidationError

from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Business   # 🔗 Бизнес моделини импорт қиламиз

class Kuryer(models.Model):
    id = models.BigAutoField(primary_key=True)        # bigserial
    sana = models.DateField()                         # date
    kuryer_id = models.BigIntegerField(unique=True)   # int8, уникал
    kuryer_name = models.CharField(max_length=55)     # varchar(55)

    avto_num = models.TextField(blank=True, null=True)    # авто рақам
    avto_marka = models.TextField(blank=True, null=True)  # авто марка
    tel_num = models.CharField(max_length=20, unique=True)  # телефон рақами

    password = models.CharField(max_length=128, blank=True, null=True)  # парол (hashed бўлиши керак)
    pin_code = models.CharField(max_length=8, blank=True, null=True)    # пин код

    grated = models.DateTimeField(auto_now_add=True)  # timestamp

    # 🟡 Тил
    lang = models.TextField(blank=True, null=True)    # 'uz' | 'ru' | 'en'

    # 🆕 Курер хизмат нархи қоидалари (диапазонли тарифлар) — JSON
    # Формат (маслаҳат): [{"period":"month","min":0,"max":5000,"price":2000,"currency":"UZS"}, ...]
    service_price_rules = models.JSONField(default=list, blank=True)

    # 🆕 Сарик устунлар
    yil_bosh_sotil_suv_soni = models.PositiveIntegerField(default=0)  # йил бошигача жами сотилган сув (дона)
    oy_bosh_sotil_suv_soni  = models.PositiveIntegerField(default=0)  # ой бошигача жами сотилган сув (дона)

    # Нарх диапазонлари қўлланадиган давр: 'month' | 'year'
    DIAP_DAVR_CHOICES = (("month", "month"), ("year", "year"))
    narxlar_diap_davri = models.CharField(max_length=8, choices=DIAP_DAVR_CHOICES, default="month")

    # 🔗 БОСС БИЗНЕСИГА БОҒЛАШ — FK (бир бизнесга кўп курьер)
    business = models.ForeignKey(
        Business,
        on_delete=models.PROTECT,      # бизнес ўчирилмасин; аввал ажратиш керак бўлади
        related_name="couriers",       # Business.objects.get(...).couriers.all()
        null=True, blank=True          # мавжуд қаторлар учун енгил миграция
    )

    class Meta:
        db_table = "kuryer"   # PostgreSQL'да жадвал номи: public.kuryer
        verbose_name = "Kuryer"
        verbose_name_plural = "Kuryerlar"
        indexes = [
            models.Index(fields=["kuryer_id"], name="idx_kuryer_id"),
            models.Index(fields=["tel_num"], name="idx_kuryer_tel"),
            models.Index(fields=["narxlar_diap_davri"], name="idx_kuryer_diap_davr"),
            models.Index(fields=["business"], name="idx_kuryer_business"),  # 🆕 тез фильтр/қидирув учун
        ]

    def __str__(self):
        return f"{self.kuryer_name} ({self.tel_num})"

    # ✅ Валидация: min/max ва бир период ичида тўқнашувни (overlap) текшириш
    def clean(self):
        rules = self.service_price_rules or []
        norm = []
        for r in rules:
            if not isinstance(r, dict):
                raise ValidationError("service_price_rules элементлари dict бўлиши керак.")
            period = (r.get("period") or "month").strip()
            mn = int(r.get("min", 0))
            mx = r.get("max", None)
            if mx is not None:
                mx = int(mx)
            price = int(r.get("price", 0))
            if mn < 0:
                raise ValidationError("Диапазон min манфий бўлмасин.")
            if mx is not None and mx < mn:
                raise ValidationError("Диапазон max >= min бўлиши керак.")
            if price <= 0:
                raise ValidationError("Нарх (price) мусбат бўлиши керак.")
            norm.append({"period": period, "min": mn, "max": mx, "price": price})

        for p in ("month", "year"):
            segs = sorted([(r["min"], r["max"]) for r in norm if r["period"] == p], key=lambda x: x[0])
            for i in range(1, len(segs)):
                prev_min, prev_max = segs[i-1]
                cur_min,  cur_max  = segs[i]
                if prev_max is None or prev_max >= cur_min:
                    raise ValidationError(f"'{p}' диапазонлари ўзаро тўқнашди.")

    # ℹ️ Ихтиёрий helper: qty ва period бўйича хизмат нархини аниқлаш
    def resolve_service_price(self, qty: int, period: str = "month") -> int:
        rules = [r for r in (self.service_price_rules or []) if (r.get("period") or "month") == period]
        rules.sort(key=lambda r: int(r.get("min", 0)))
        for r in rules:
            mn = int(r.get("min", 0))
            mx = r.get("max", None)
            mx = int(mx) if mx is not None else None
            if qty >= mn and (mx is None or qty <= mx):
                return int(r.get("price", 0))
        return 0


