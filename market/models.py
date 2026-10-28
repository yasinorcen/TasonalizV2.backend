"""
Database models for Tasonaliz:
- Company: All Borsa İstanbul (BIST) companies synced from KAP directory
- FinancialStatementCache: Cached KAP/IFRS financial statement periods per company
- Comment: User comments linked to either a Company or a specific Financial Statement/Period
"""

from django.contrib.auth.models import User
from django.db import models


class Company(models.Model):
    code = models.CharField(
        max_length=16,
        unique=True,
        db_index=True,
        verbose_name="Hisse Kodu",
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        verbose_name="Şirket Unvanı",
    )
    sector = models.CharField(
        max_length=150,
        blank=True,
        default="Borsa İstanbul Şirketi",
        verbose_name="Sektör / Kategori",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Şehir",
    )
    indices = models.CharField(
        max_length=200,
        blank=True,
        default="BIST TÜM",
        verbose_name="Dahil Olduğu Endeksler",
    )
    kap_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="Resmî KAP Şirket Sayfası",
    )
    is_bist30 = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="BIST 30 Şirketi mi?",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Şirket"
        verbose_name_plural = "Şirketler"

    def __str__(self):
        return f"{self.code} - {self.name}"


class Comment(models.Model):
    class TargetType(models.TextChoices):
        COMPANY = "COMPANY", "Şirket / Hisse Sayfası"
        FINANCIAL_TABLE = "FINANCIAL_TABLE", "Finansal Tablo / Dönem"

    class StatementType(models.TextChoices):
        NONE = "", "Genel (Şirket)"
        BILANCO = "BILANCO", "Bilanço"
        GELIR = "GELIR", "Gelir Tablosu"
        NAKIT = "NAKIT", "Nakit Akış Tablosu"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Yazar",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="İlgili Şirket",
    )
    target_type = models.CharField(
        max_length=20,
        choices=TargetType.choices,
        default=TargetType.COMPANY,
        db_index=True,
        verbose_name="Hedef Türü",
    )
    statement_type = models.CharField(
        max_length=20,
        choices=StatementType.choices,
        blank=True,
        default=StatementType.NONE,
        db_index=True,
        verbose_name="Tablo Türü",
    )
    period = models.CharField(
        max_length=32,
        blank=True,
        default="",
        db_index=True,
        verbose_name="İlgili Raporlama Dönemi",
    )
    content = models.TextField(
        max_length=2000,
        verbose_name="Yorum Metni",
    )
    is_edited = models.BooleanField(
        default=False,
        verbose_name="Düzenlendi mi?",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Oluşturulma Zamanı",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Son Güncellenme Zamanı",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Kullanıcı Yorumu"
        verbose_name_plural = "Kullanıcı Yorumları"

    def __str__(self):
        return f"{self.user.username} -> {self.company.code} ({self.target_type})"
