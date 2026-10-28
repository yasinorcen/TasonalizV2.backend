# Tasonaliz Backend API (Django + DRF)

**Tasonaliz**; Borsa İstanbul (BIST) şirketlerine ait hisse fiyatlarını, KAP finansal tablolarını (Bilanço, Gelir Tablosu, Nakit Akış Tablosu), sadeleştirilmiş temel finansal analizleri, şirket haberlerini, altın/gümüş/emtia verilerini ve kullanıcı yorumlarını sunan öğrenci amaçlı bilgilendirme ve simülasyon projesinin backend servisidir.

> **Önemli Uyarı:** Tasonaliz alım-satım işlemi gerçekleştirmez, aracı kurum bağlantısı içermez ve yatırım tavsiyesi sunmaz.

## Teknoloji Yığını

- **Dil & Framework:** Python 3.11+ / Django & Django REST Framework (DRF)
- **Kimlik Doğrulama:** JWT (`djangorestframework-simplejwt`) + Django yerleşik parola doğrulama
- **Veritabanı:** PostgreSQL (`DATABASE_URL` / `psycopg[binary]`) ve yerel geliştirme için opsiyonel SQLite desteği
- **Veri Sağlayıcılar (Modüler Adapter Katmanı):**
  - Resmî KAP BIST Şirketler Dizini (`https://www.kap.org.tr/tr/bist-sirketler`) — Tüm BIST şirketleri
  - Hisse Fiyatları ve Tarihsel Seri (`yfinance` `.IS` gecikmeli piyasa verisi)
  - Finansal Tablolar (`Bilanço`, `Gelir Tablosu`, `Nakit Akış Tablosu`) ve KAP Bildirim Bağlantıları
  - Haberler (Google News RSS & KAP bağlantıları — telif kurallarına uygun olarak yalnızca başlık, tarih, kaynak adı ve orijinal bağlantı)
  - Altın, Gümüş ve Bronz/Bakır Emtia Verileri

## Kurulum (Yerel Geliştirme)

```bash
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py sync_bist
python manage.py runserver
```

## Testleri Çalıştırma

```bash
python manage.py test
```

## Veritabanı Yedekleme ve Geri Yükleme Planı (PostgreSQL)

- **Yedekleme (Backup):**
  ```bash
  pg_dump "$DATABASE_URL" --format=custom --file=tasonaliz_backup_$(date +%Y%m%d).dump
  ```
- **Geri Yükleme (Restore):**
  ```bash
  pg_restore --clean --no-acl --no-owner -d "$DATABASE_URL" tasonaliz_backup_YYYYMMDD.dump
  ```
