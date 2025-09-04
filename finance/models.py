from django.db import models, transaction
from django.core.exceptions import ValidationError
from accounts.models import Business  # тенант

class CashBoss(models.Model):
    business = models.ForeignKey(Business, on_delete=models.PROTECT, null=True, blank=True)
    sana = models.DateField()
    vaqt = models.TimeField()

    boss_id = models.BigIntegerField()
    boss_name = models.CharField(max_length=55)

    client_tg_id = models.BigIntegerField(blank=True, null=True)
    client_tel_num = models.CharField(max_length=15, blank=True, null=True)

    buyurtma_num = models.BigIntegerField(blank=True, null=True)
    kuryer_id = models.BigIntegerField()
    kuryer_name = models.CharField(max_length=55)

    income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    OPERATION = (("income", "Income"), ("expense", "Expense"))
    cash_operation = models.CharField(max_length=10, choices=OPERATION)

    cash_message = models.CharField(max_length=255, blank=True)
    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cash_boss"
        verbose_name = "Босс касса ҳисоби"
        verbose_name_plural = "Босс касса ҳисоби"
        indexes = [
            models.Index(fields=["business", "boss_id"]),
            models.Index(fields=["business", "kuryer_id"]),
        ]

    def save(self, *args, **kwargs):
        if self.cash_operation == "income":
            self.cash_message = f"Курер {self.kuryer_name} дан кирим булди"
        else:
            self.cash_message = "Нақд пул топширилди"
        super().save(*args, **kwargs)


class CashState(models.Model):
    """Босс тасдиғидан олдинги холатлар."""
    business = models.ForeignKey(Business, on_delete=models.PROTECT)
    sana = models.DateField()
    vaqt = models.TimeField()

    boss_id = models.BigIntegerField()
    boss_name = models.CharField(max_length=55)

    kuryer_id = models.BigIntegerField()
    kuryer_name = models.CharField(max_length=55)

    income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0, help_text="Тасдиқ пайтида ҳисобланади")

    OPERATION = (("income", "Income"), ("expense", "Expense"))
    cash_operation = models.CharField(max_length=10, choices=OPERATION)

    STATUS = (("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"))
    status = models.CharField(max_length=10, choices=STATUS, default="pending")

    tasdiq_vaqti = models.DateTimeField(blank=True, null=True)
    rad_vaqti = models.DateTimeField(blank=True, null=True)

    # тасдиқланганда яратилган CashBoss ёзувига сслка
    cash_boss = models.OneToOneField(CashBoss, on_delete=models.SET_NULL, null=True, blank=True, related_name="source_state")

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cash_state"
        verbose_name = "Касса ҳолати"
        verbose_name_plural = "Касса ҳолати"
        indexes = [
            models.Index(fields=["business", "boss_id", "status"]),
            models.Index(fields=["business", "kuryer_id", "status"]),
        ]

    def clean(self):
        if self.cash_operation == "income":
            if self.income <= 0 or self.expense != 0:
                raise ValidationError("Income учун income>0 ва expense=0 бўлиши керак.")
        if self.cash_operation == "expense":
            if self.expense <= 0 or self.income != 0:
                raise ValidationError("Expense учун expense>0 ва income=0 бўлиши керак.")

    @transaction.atomic
    def approve(self, now_dt):
        """Босс тасдиқлаганда CashBoss’га ўтказиш ва балансни янгилаш."""
        if self.status != "pending":
            return self.cash_boss  # олдин ишланган

        # олдинги баланс
        last = (
            CashBoss.objects
            .filter(business=self.business, boss_id=self.boss_id)
            .order_by("-grated")
            .first()
        )
        prev_balance = last.balance if last else 0

        new_balance = prev_balance + (self.income or 0) - (self.expense or 0)

        boss = CashBoss.objects.create(
            business=self.business,
            sana=self.sana,
            vaqt=self.vaqt,
            boss_id=self.boss_id,
            boss_name=self.boss_name,
            kuryer_id=self.kuryer_id,
            kuryer_name=self.kuryer_name,
            income=self.income,
            expense=self.expense,
            balance=new_balance,
            cash_operation=self.cash_operation,
        )

        self.cash_boss = boss
        self.balance = new_balance
        self.status = "approved"
        self.tasdiq_vaqti = now_dt
        self.save(update_fields=["cash_boss", "balance", "status", "tasdiq_vaqti"])
        return boss

    def reject(self, now_dt):
        """Босс рад этса — CashBoss’га ўтказилмайди."""
        if self.status == "pending":
            self.status = "rejected"
            self.rad_vaqti = now_dt
            self.save(update_fields=["status", "rad_vaqti"])



class CashKuryer(models.Model):
    """
    Курьер кассаси жадвали.
    Клиентдан нақд сотувлар → КИРИМ.
    Боссга пул топшириш → ЧИҚИМ (аввал CashState’га, тасдиқдан сўнг CashBoss’га кўчади).
    """
    id = models.BigAutoField(primary_key=True)   # bigserial
    sana = models.DateField()                   # сана
    vaqt = models.TimeField()                   # вақт

    boss_id = models.BigIntegerField()
    boss_name = models.CharField(max_length=55)

    client_tg_id = models.BigIntegerField()
    client_tel_num = models.CharField(max_length=15)

    buyurtma_num = models.BigIntegerField()     # буюртма рақами (лог учун)
    kuryer_id = models.BigIntegerField()
    kuryer_name = models.CharField(max_length=55)

    # 💰 Суммалар
    income  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # 🔁 Операция тури
    OPERATION_CHOICES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]
    cash_operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)

    # 📊 Ҳолат
    STATUS_CHOICES = [
        ("buffer", "Buffer"),          # курьер киритган, тасдиқланмаган
        ("approved", "Tasdiqlandi"),   # босс тасдиқлаган
        ("rejected", "Rad etildi"),    # рад этилган
    ]
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="buffer")

    grated = models.DateTimeField(auto_now_add=True)  # timestamp

    class Meta:
        db_table = "cash_kuryer"
        verbose_name = "Курер касса ҳисоби"
        verbose_name_plural = "Курер касса ҳисоби"
        indexes = [
            models.Index(fields=["boss_id"], name="idx_ck_boss"),
            models.Index(fields=["kuryer_id"], name="idx_ck_kuryer"),
            models.Index(fields=["client_tel_num"], name="idx_ck_client_tel"),
            models.Index(fields=["buyurtma_num"], name="idx_ck_buyurtma"),
            models.Index(fields=["status"], name="idx_ck_status"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} | Kuryer: {self.kuryer_name} | Balance: {self.balance}"

    # ✅ Валидация: 'income' / 'expense' текшириш
    def clean(self):
        super().clean()
        if self.cash_operation == "income":
            if self.income <= 0:
                raise ValidationError("Income операциясида 'income' > 0 бўлиши керак.")
            if self.expense > 0:
                raise ValidationError("Income операциясида 'expense' 0 бўлиши керак.")
        elif self.cash_operation == "expense":
            if self.expense <= 0:
                raise ValidationError("Expense операциясида 'expense' > 0 бўлиши керак.")
            if self.income > 0:
                raise ValidationError("Expense операциясида 'income' 0 бўлиши керак.")
            
class CourierWaterBottleBalance(models.Model):
    """
    Курьер тўла сув (19L бак) ҳаракатлари ва қолдиқлари журнали.
    - in_from_boss: Боссдан олинди → water_balance++, bottle_balance++
    - sell_to_client: Мижозга сотилди → water_balance--, bottle_balance--
    - return_empty: Мижоз бўш тарa қайтaрди → баланс ўзгармайди (лойиҳа сиёсатига кўра)
    - adjustment: Қўлда тузатиш
    """
    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(Business, on_delete=models.PROTECT)

    sana = models.DateField()
    vaqt = models.TimeField()

    boss_id = models.BigIntegerField()
    boss_name = models.CharField(max_length=55)

    client_tg_id = models.BigIntegerField(blank=True, null=True)
    client_tel_num = models.CharField(max_length=15, blank=True, null=True)

    buyurtma_num = models.BigIntegerField(blank=True, null=True)

    kuryer_id = models.BigIntegerField()
    kuryer_name = models.CharField(max_length=55)

    # 🔢 Ҳаракат миқдори (дона). Пул эмас!
    income = models.PositiveIntegerField(default=0)   # кирим (дона)
    expense = models.PositiveIntegerField(default=0)  # чиқим (дона)

    # 🔁 Операция тури
    OPERATION = (
        ("in_from_boss", "In from Boss"),
        ("sell_to_client", "Sell to Client"),
        ("return_empty", "Return Empty"),
        ("adjustment", "Adjustment"),
    )
    operation = models.CharField(max_length=20, choices=OPERATION)

    # 📊 Қолдиқлар (дона).
    # water_balance: курьер қўлидаги тўла сув баклар сони
    # bottle_balance: тўла бак “тарa” ҳисобининг қолдиғи (лойиҳа сиёсатига кўра бўш қайтганда ўзгармайди)
    water_balance = models.PositiveIntegerField(default=0)
    bottle_balance = models.PositiveIntegerField(default=0)

    STATUS = (("ok", "OK"), ("draft", "Draft"), ("void", "Void"))
    status = models.CharField(max_length=10, choices=STATUS, default="ok")

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "kuryer_water_bottle_balance"
        verbose_name = "Курер сув ва тара ҳисоби"
        verbose_name_plural = "Курер сув ва тара ҳисоби"
        indexes = [
            models.Index(fields=["business", "kuryer_id", "sana", "vaqt"], name="idx_kwbb_kur_dt"),
            models.Index(fields=["business", "boss_id"], name="idx_kwbb_boss"),
            models.Index(fields=["business", "operation"], name="idx_kwbb_op"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} | {self.kuryer_name} | W:{self.water_balance} B:{self.bottle_balance}"

    # ✅ Текшириш: operation ↔ income/expense мослиги
    def clean(self):
        super().clean()
        if self.operation == "in_from_boss":
            if self.income <= 0 or self.expense != 0:
                raise ValidationError("in_from_boss: income>0 ва expense=0 бўлиши керак.")
        elif self.operation == "sell_to_client":
            if self.expense <= 0 or self.income != 0:
                raise ValidationError("sell_to_client: expense>0 ва income=0 бўлиши керак.")
        elif self.operation == "return_empty":
            # баланс ўзгармайди, шунинг учун ҳар иккаласи ҳам 0 бўлиши керак
            if self.income != 0 or self.expense != 0:
                raise ValidationError("return_empty: income=0 ва expense=0 бўлиши керак.")
        elif self.operation == "adjustment":
            # adjustment’да ҳар иккаласи ҳам 0 бўлмасин (кичик тузатишга руҳсат)
            if self.income == 0 and self.expense == 0:
                raise ValidationError("adjustment: income ёки expense дан камида бири > 0 бўлиши керак.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Автоматик қолдиқ ҳисоблаш:
        - in_from_boss:  +income
        - sell_to_client: -expense
        - return_empty:   0 (баланс ўзгармайди)
        - adjustment:     +income -expense
        """
        is_new = self._state.adding

        if is_new:
            # олдинги ҳолатни оламиз (шу курьер + бизнес бўйича)
            last = (
                CourierWaterBottleBalance.objects
                .select_for_update()
                .filter(business=self.business, kuryer_id=self.kuryer_id, status="ok")
                .order_by("-grated")
                .first()
            )
            prev_water = last.water_balance if last else 0
            prev_bottle = last.bottle_balance if last else 0

            delta = 0
            if self.operation == "in_from_boss":
                delta = self.income
            elif self.operation == "sell_to_client":
                delta = -self.expense
            elif self.operation == "return_empty":
                delta = 0
            elif self.operation == "adjustment":
                delta = self.income - self.expense

            # Ҳар иккала баланс бир хил қадам билан ўзгаради
            self.water_balance = max(0, prev_water + delta)
            self.bottle_balance = max(0, prev_bottle + delta)

        super().save(*args, **kwargs)
        

class BossSystemAccount(models.Model):
    """
    Босс (тадбиркор) ва тизим ҳисоб-китоб жадвали.
    - income: Босс онлайн тўлов қилиб балансини тўлдирди
    - expense: Сув сотилганда тизим ҳисобидан ечилди
    """
    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(Business, on_delete=models.PROTECT)  # қайси тадбиркор

    sana = models.DateField()
    vaqt = models.TimeField()

    # 💰 Суммалар
    income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    OPERATION = (
        ("income", "Income (Top-up)"),
        ("expense", "Expense (Water Sale)"),
        ("promo", "Promo/Free"),  # акция ёки рекламадан
    )
    operation = models.CharField(max_length=10, choices=OPERATION)

    # Изоҳ / лог
    note = models.CharField(max_length=255, blank=True, null=True)

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "boss_system_account"
        verbose_name = "Тизим ҳисоби"
        verbose_name_plural = "Тизим ҳисоби"
        indexes = [
            models.Index(fields=["business", "sana"], name="idx_bsa_biz_sana"),
            models.Index(fields=["business", "operation"], name="idx_bsa_biz_op"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} | {self.business.name} | Balance: {self.balance}"

    def clean(self):
        super().clean()
        if self.operation == "income":
            if self.income <= 0 or self.expense != 0:
                raise ValidationError("Income учун income>0 ва expense=0 бўлиши керак.")
        elif self.operation == "expense":
            if self.expense <= 0 or self.income != 0:
                raise ValidationError("Expense учун expense>0 ва income=0 бўлиши керак.")
        elif self.operation == "promo":
            if self.income != 0 or self.expense != 0:
                raise ValidationError("Promo операциясида income=0 ва expense=0 бўлиши керак.")

    def save(self, *args, **kwargs):
        # Олдинги балансни олиб, янгилаймиз
        last = (
            BossSystemAccount.objects
            .filter(business=self.business)
            .order_by("-grated")
            .first()
        )
        prev_balance = last.balance if last else 0

        if self.operation == "income":
            self.balance = prev_balance + self.income
            self.note = self.note or "Босс балансини онлайн тўлдирди"
        elif self.operation == "expense":
            self.balance = prev_balance - self.expense
            self.note = self.note or "Сув сотилди, ҳисобдан ечилди"
        elif self.operation == "promo":
            self.balance = prev_balance
            self.note = self.note or "Акция/реклама — хақ олинмади"

        super().save(*args, **kwargs)



class WaterPricePlan(models.Model):
    business   = models.ForeignKey(Business, on_delete=models.PROTECT, related_name="price_plans")
    name       = models.CharField(max_length=60, default="Асосий нарх")
    period     = models.CharField(
        max_length=8,
        choices=(("month", "Ой"), ("year", "Йил")),
        default="month"
    )
    currency   = models.CharField(max_length=8, default="UZS")
    is_active  = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)   # акция бошланиши
    end_date   = models.DateField(null=True, blank=True)   # акция тугаши
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "water_price_plan"
        verbose_name = "Сув нарх режаси"
        verbose_name_plural = "Сув нарх режалари"
        indexes = [
            models.Index(fields=["business", "is_active"]),
            models.Index(fields=["business", "period"]),
        ]

    def __str__(self):
        return f"{self.business} — {self.name}"


class WaterPriceTier(models.Model):
    plan       = models.ForeignKey(WaterPricePlan, on_delete=models.CASCADE, related_name="tiers")
    min_qty    = models.PositiveIntegerField(default=0)
    max_qty    = models.PositiveIntegerField(null=True, blank=True)  # None → ∞
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)  # сўм
    priority   = models.PositiveSmallIntegerField(default=100)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "water_price_tier"
        verbose_name = "Сув нарх диапазони"
        verbose_name_plural = "Сув нарх диапазонлари"
        ordering = ["priority", "min_qty"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(max_qty__isnull=True) | models.Q(max_qty__gte=models.F("min_qty")),
                name="tier_min_lte_max",
            )
        ]
        indexes = [
            models.Index(fields=["plan", "is_active"]),
            models.Index(fields=["plan", "min_qty", "max_qty"]),
        ]

    def __str__(self):
        hi = self.max_qty if self.max_qty is not None else "∞"
        return f"{self.plan.name}: {self.min_qty}–{hi} дона → {self.unit_price} {self.plan.currency}"
