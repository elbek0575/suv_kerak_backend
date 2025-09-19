from django.db import models, transaction
from django.core.exceptions import ValidationError
from accounts.models import Business  # тенант
from django.utils import timezone

class CashMenedjer(models.Model):
    business = models.ForeignKey(Business, on_delete=models.PROTECT, null=True, blank=True)

    sana = models.DateField()
    vaqt = models.TimeField()

    # 🔁 қайта номланган устунлар
    menedjer_id   = models.BigIntegerField()
    menedjer_name = models.CharField(max_length=55)

    client_tg_id   = models.BigIntegerField(blank=True, null=True)
    client_tel_num = models.CharField(max_length=15, blank=True, null=True)

    buyurtma_num = models.BigIntegerField(blank=True, null=True)
    kuryer_id    = models.BigIntegerField()
    kuryer_name  = models.CharField(max_length=55)

    income  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # скринда: status (text), cash_operation (text)
    status         = models.TextField(blank=True, null=True)
    cash_operation = models.TextField()  # ('income' | 'expense' ёки матн)

    cash_message = models.CharField(max_length=255, blank=True)
    grated       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cash_menedjer"
        verbose_name = "Menedjer kassa"
        verbose_name_plural = "Menedjer kassa yozувлари"
        indexes = [
            models.Index(fields=["business", "menedjer_id"], name="idx_cash_menedjer_mgr"),
            models.Index(fields=["business", "kuryer_id"],   name="idx_cash_menedjer_kur"),
        ]

    def save(self, *args, **kwargs):
        # Автоматик хабар (хоҳласангиз матнни ўзгартиришингиз мумкин)
        if (self.cash_operation or "").lower() == "income":
            self.cash_message = f"Курьер {self.kuryer_name} дан кирим бўлди"
        elif (self.cash_operation or "").lower() == "expense":
            self.cash_message = "Нақд пул топширилди"
        super().save(*args, **kwargs)


class CashState(models.Model):
    """Босс тасдиғидан олдинги ҳолатлар (энди: менежер)."""
    business = models.ForeignKey(Business, on_delete=models.PROTECT)
    sana = models.DateField()
    vaqt = models.TimeField()

    # 🟡 қайта номланган устунлар
    menedjer_id   = models.BigIntegerField()                 # old: boss_id
    menedjer_name = models.CharField(max_length=55)          # old: boss_name

    kuryer_id = models.BigIntegerField()
    kuryer_name = models.CharField(max_length=55)

    income  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text="Тасдиқ пайтида ҳисобланади"
    )

    OPERATION = (("income", "Income"), ("expense", "Expense"))
    cash_operation = models.CharField(max_length=10, choices=OPERATION)

    STATUS = (("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected"))
    status = models.CharField(max_length=10, choices=STATUS, default="pending")

    tasdiq_vaqti = models.DateTimeField(blank=True, null=True)
    rad_vaqti    = models.DateTimeField(blank=True, null=True)

    # тасдиқланганда яратилган CashMenedjer ёзувига ссилка
    cash_boss = models.OneToOneField(  # номини ҳозирча ўзгартирмай қолдирдик
        CashMenedjer, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="source_state"
    )

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cash_state"
        verbose_name = "Касса ҳолати"
        verbose_name_plural = "Касса ҳолати"
        indexes = [
            models.Index(fields=["business", "menedjer_id", "status"]),  # old: boss_id
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
        """Менежер тасдиқлаганда CashMenedjer’га ўтказиш ва балансни янгилаш."""
        if self.status != "pending":
            return self.cash_boss  # олдин ишланган

        # олдинги баланс (энди CashMenedjer бўйича)
        last = (
            CashMenedjer.objects
            .filter(business=self.business, menedjer_id=self.menedjer_id)
            .order_by("-grated")
            .first()
        )
        prev_balance = last.balance if last else 0
        new_balance = prev_balance + (self.income or 0) - (self.expense or 0)

        boss = CashMenedjer.objects.create(
            business=self.business,
            sana=self.sana,
            vaqt=self.vaqt,
            menedjer_id=self.menedjer_id,
            menedjer_name=self.menedjer_name,
            kuryer_id=self.kuryer_id,
            kuryer_name=self.kuryer_name,
            income=self.income,
            expense=self.expense,
            balance=new_balance,
            cash_operation=self.cash_operation,
        )

        self.cash_boss  = boss
        self.balance    = new_balance
        self.status     = "approved"
        self.tasdiq_vaqti = now_dt
        self.save(update_fields=["cash_boss", "balance", "status", "tasdiq_vaqti"])
        return boss

    def reject(self, now_dt):
        """Менежер рад этса — CashMenedjer’га ўтмайди."""
        if self.status == "pending":
            self.status = "rejected"
            self.rad_vaqti = now_dt
            self.save(update_fields=["status", "rad_vaqti"])



class CashKuryer(models.Model):
    """Курьер кассаси."""
    business = models.ForeignKey(Business, on_delete=models.PROTECT, null=True, blank=True)

    id   = models.BigAutoField(primary_key=True)
    sana = models.DateField()
    vaqt = models.TimeField()

    # 🟡 Менежерга ўтказилди
    menedjer_id   = models.BigIntegerField()
    menedjer_name = models.CharField(max_length=55)

    client_tg_id   = models.BigIntegerField(blank=True, null=True)
    client_tel_num = models.CharField(max_length=15, blank=True, null=True)

    buyurtma_num = models.BigIntegerField(blank=True, null=True)
    kuryer_id    = models.BigIntegerField()
    kuryer_name  = models.CharField(max_length=55)

    # 💰 Суммалар
    income  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # 🔁 Скринда — text
    cash_operation = models.TextField()  # 'income' | 'expense' (матн)
    status         = models.TextField(blank=True, null=True)  # 'buffer' | 'approved' | 'rejected'

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cash_kuryer"
        verbose_name = "Курер касса ҳисоби"
        verbose_name_plural = "Курер касса ҳисоби"
        indexes = [
            models.Index(fields=["business", "menedjer_id"], name="idx_ck_mgr"),
            models.Index(fields=["business", "kuryer_id"],   name="idx_ck_kuryer"),
            models.Index(fields=["client_tel_num"],          name="idx_ck_client_tel"),
            models.Index(fields=["buyurtma_num"],            name="idx_ck_buyurtma"),
            models.Index(fields=["status"],                  name="idx_ck_status"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} | Kuryer: {self.kuryer_name} | Balance: {self.balance}"

    # ✅ Валидация (матнга қарамай ҳозирча шу қоида)
    def clean(self):
        op = (self.cash_operation or "").lower()
        if op == "income":
            if self.income <= 0 or self.expense != 0:
                raise ValidationError("Income операциясида income>0 ва expense=0 бўлиши керак.")
        elif op == "expense":
            if self.expense <= 0 or self.income != 0:
                raise ValidationError("Expense операциясида expense>0 ва income=0 бўлиши керак.")
            
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

    # 🟡 қайта номланган устунлар
    menedjer_id   = models.BigIntegerField()            # old: boss_id
    menedjer_name = models.CharField(max_length=55)     # old: boss_name

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
            models.Index(fields=["business", "menedjer_id"], name="idx_kwbb_menedjer"),  # old: boss_id
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
        

class BusinessSystemAccount(models.Model):
    """
    Босс (тадбиркор) ва тизим ҳисоб-китоб жадвали.
    - income: Босс онлайн тўлов қилиб балансини тўлдирди
    - expense: Сув сотилганда тизим ҳисобидан ечилди
    """
    from django.db import models
from django.core.exceptions import ValidationError
from accounts.models import Business

class BusinessSystemAccount(models.Model):
    """Тизим ҳисоби (скринга мос)."""
    id = models.BigAutoField(primary_key=True)
    business = models.ForeignKey(Business, on_delete=models.PROTECT)

    sana = models.DateField()
    vaqt = models.TimeField()

    # 🟡 скриндаги сарик устунлар
    menedjer_id   = models.BigIntegerField(blank=True, null=True)
    menedjer_name = models.CharField(max_length=55, blank=True, null=True)

    client_tg_id  = models.BigIntegerField(blank=True, null=True)
    buyurtma_num  = models.BigIntegerField(blank=True, null=True)

    kuryer_id   = models.BigIntegerField(blank=True, null=True)   # <-- null=True
    kuryer_name = models.CharField(max_length=55, blank=True, null=True)

    tulov_tizimi = models.TextField(blank=True, null=True)

    income  = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tizimdagi_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    status    = models.TextField(blank=True, null=True)
    operation = models.TextField()

    grated = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "business_system_account"
        verbose_name = "Бизнес тизим ҳисоби"
        verbose_name_plural = "Бизнес тизим ҳисоби"
        indexes = [
            models.Index(fields=["business", "sana"],        name="idx_bsa_biz_sana"),
            models.Index(fields=["business", "menedjer_id"], name="idx_bsa_mgr"),
            models.Index(fields=["business", "kuryer_id"],   name="idx_bsa_kur"),
            models.Index(fields=["business", "operation"],   name="idx_bsa_op"),
            models.Index(fields=["business", "status"],      name="idx_bsa_status"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} | {self.business.name} | Bal: {self.tizimdagi_balance}"

    def clean(self):
        op = (self.operation or "").lower()
        if op == "income":
            if self.income <= 0 or self.expense != 0:
                raise ValidationError("Income учун income>0 ва expense=0 бўлсин.")
        elif op == "expense":
            if self.expense <= 0 or self.income != 0:
                raise ValidationError("Expense учун expense>0 ва income=0 бўлсин.")
        # promo/бошқаларга қоида қўймасак ҳам бўлади

    def save(self, *args, **kwargs):
        # бир бизнес бўйича охирги балансни топиб, янгилаймиз
        last = (
            BusinessSystemAccount.objects
            .filter(business=self.business)
            .order_by("-grated")
            .first()
        )
        prev = last.tizimdagi_balance if last else 0

        op = (self.operation or "").lower()
        if op == "income":
            self.tizimdagi_balance = prev + self.income
        elif op == "expense":
            self.tizimdagi_balance = prev - self.expense
        else:
            self.tizimdagi_balance = prev  # promo/бошқа турлар

        super().save(*args, **kwargs)
        
class Transaction(models.Model):
    class Status(models.TextChoices):
        PENDING   = "pending",   "pending"
        SUCCESS   = "success",   "success"
        FAILED    = "failed",    "failed"
        CANCELED  = "canceled",  "canceled"

    # id: serial4
    id = models.AutoField(primary_key=True)

    # transaction_id: varchar(50)
    transaction_id = models.CharField(max_length=50, db_index=True)

    # order_id: varchar(50)
    order_id = models.CharField(max_length=50, db_index=True)

    # amount: numeric(12,2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    # status: varchar(20)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    # created_at: timestamptz
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    # updated_at: timestamptz
    updated_at = models.DateTimeField(auto_now=True)

    # cancel_time: timestamptz
    cancel_time = models.DateTimeField(null=True, blank=True)

    # reason: int4 (масалан, бекор қилиш сабаб коди)
    reason = models.IntegerField(null=True, blank=True)

    # id_tg_client: int8
    id_tg_client = models.BigIntegerField(null=True, blank=True)

    # tel_num_client: varchar(45)
    tel_num_client = models.CharField(max_length=45, null=True, blank=True)

    class Meta:
        db_table = "transactions"
        indexes = [
            models.Index(fields=["transaction_id"]),
            models.Index(fields=["order_id"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.transaction_id} | {self.order_id} | {self.status} | {self.amount}"