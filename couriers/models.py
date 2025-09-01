from django.db import models

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

    class Meta:
        db_table = "kuryer"   # PostgreSQL'да жадвал номи: public.kuryer
        verbose_name = "Kuryer"
        verbose_name_plural = "Kuryerlar"
        indexes = [
            models.Index(fields=["kuryer_id"], name="idx_kuryer_id"),
            models.Index(fields=["tel_num"], name="idx_kuryer_tel"),
        ]

    def __str__(self):
        return f"{self.kuryer_name} ({self.tel_num})"

