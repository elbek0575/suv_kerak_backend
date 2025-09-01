from django.db import models
from django.core.exceptions import ValidationError

class CashBoss(models.Model):
    id = models.BigAutoField(primary_key=True)      # bigserial
    sana = models.DateField()                       # date
    vaqt = models.TimeField()                       # time

    boss_id = models.BigIntegerField()
    boss_name = models.CharField(max_length=55)

    client_tg_id = models.BigIntegerField()
    client_tel_num = models.CharField(max_length=15)

    buyurtma_num = models.BigIntegerField()
    kuryer_id = models.BigIntegerField()
    kuryer_name = models.CharField(max_length=55)

    income = models.DecimalField(max_digits=14, decimal_places=2, default=0)   # кирим
    expense = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # чиқим
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # қолдиқ

    OPERATION_CHOICES = [
        ("income", "Income"),
        ("expense", "Expense"),
    ]
    cash_operation = models.CharField(max_length=10, choices=OPERATION_CHOICES)

    # 🟢 Автоматик изоҳ (лог) — операцияга қараб тўлади
    cash_message = models.CharField(max_length=255, blank=True)

    grated = models.DateTimeField(auto_now_add=True)  # timestamp

    class Meta:
        db_table = "cash_boss"
        verbose_name = "Boss Kassa"
        verbose_name_plural = "Boss Kassalari"
        indexes = [
            models.Index(fields=["boss_id"], name="idx_cashboss_boss"),
            models.Index(fields=["client_tel_num"], name="idx_cashboss_client_tel"),
            models.Index(fields=["kuryer_id"], name="idx_cashboss_kuryer"),
        ]

    def __str__(self):
        return f"{self.sana} {self.vaqt} - Boss: {self.boss_name} | Balance: {self.balance}"

    # ✅ Валидация: income/expense мувофиқлиги
    def clean(self):
        super().clean()
        if self.cash_operation == "income":
            if self.income <= 0:
                raise ValidationError("Income операциясида 'income' > 0 бўлиши керак.")
            if self.expense > 0:
                raise ValidationError("Income операциясида 'expense' 0 бўлиши керак.")
        if self.cash_operation == "expense":
            if self.expense <= 0:
                raise ValidationError("Expense операциясида 'expense' > 0 бўлиши керак.")
            if self.income > 0:
                raise ValidationError("Expense операциясида 'income' 0 бўлиши керак.")

    # ✅ Автоматик хабар тайёрлаш
    def save(self, *args, **kwargs):
        if self.cash_operation == "income":
            self.cash_message = f"Курер {self.kuryer_name} дан кирим булди"
        elif self.cash_operation == "expense":
            self.cash_message = "Нақд пул топширилди"
        super().save(*args, **kwargs)
