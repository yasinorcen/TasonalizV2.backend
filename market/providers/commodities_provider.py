"""
Precious Metals & Commodities Provider (Section 3.5).
Covers:
- Gram Altın (24 Ayar)
- Çeyrek Altın
- Yarım Altın
- Tam Altın
- Cumhuriyet Altını
- Ons Altın (USD)
- Gümüş (Gram TRY & Ons USD)
- Bronz (Alaşımlı metal borsa durumu ve ana bileşen Bakır referansı)

Strictly follows Section 3.5:
- Never invents data if a free source does not publish a standardized ticker (e.g., Bronze alloy).
- Clearly shows unit, currency, bid/ask or spot calculation note, source name, and update time.
"""

import logging
import math
from typing import Any
from django.core.cache import cache
from django.utils import timezone
import yfinance as yf

logger = logging.getLogger(__name__)

TROY_OUNCE_TO_GRAM = 31.1034768


def _clean_float(val: Any, digits: int = 2) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None


def _fetch_yf_pair(symbol: str) -> dict:
    try:
        fast = yf.Ticker(symbol).fast_info
        lp = _clean_float(fast.get("lastPrice"), 4)
        pc = _clean_float(fast.get("previousClose") or fast.get("regularMarketPreviousClose"), 4)
        dh = _clean_float(fast.get("dayHigh"), 4)
        dl = _clean_float(fast.get("dayLow"), 4)
        chg_pct = None
        if lp is not None and pc and pc > 0:
            chg_pct = round(((lp - pc) / pc) * 100, 2)
        return {
            "last": lp,
            "prev": pc,
            "high": dh,
            "low": dl,
            "change_percent": chg_pct,
        }
    except Exception as exc:
        logger.warning("Failed to fetch commodity ticker %s: %s", symbol, exc)
        return {"last": None, "prev": None, "high": None, "low": None, "change_percent": None}


def get_precious_metals_and_commodities() -> dict:
    """
    Returns structured price information for Gold types, Silver, and Bronze/Copper.
    """
    cache_key = "precious_metals_commodities_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    now_iso = timezone.now().isoformat()

    usd_try = _fetch_yf_pair("TRY=X")
    gold_oz = _fetch_yf_pair("GC=F")
    silver_oz = _fetch_yf_pair("SI=F")
    copper_lb = _fetch_yf_pair("HG=F")

    fx_rate = usd_try["last"]
    gold_usd = gold_oz["last"]
    silver_usd = silver_oz["last"]
    copper_usd = copper_lb["last"]

    gram_altin = None
    gram_altin_prev = None
    gram_altin_chg = None
    if gold_usd and fx_rate:
        gram_altin = round((gold_usd / TROY_OUNCE_TO_GRAM) * fx_rate, 2)
        if gold_oz["prev"] and usd_try["prev"]:
            gram_altin_prev = round((gold_oz["prev"] / TROY_OUNCE_TO_GRAM) * usd_try["prev"], 2)
            if gram_altin_prev > 0:
                gram_altin_chg = round(((gram_altin - gram_altin_prev) / gram_altin_prev) * 100, 2)

    gram_gumus = None
    gram_gumus_chg = None
    if silver_usd and fx_rate:
        gram_gumus = round((silver_usd / TROY_OUNCE_TO_GRAM) * fx_rate, 2)
        if silver_oz["prev"] and usd_try["prev"]:
            prev_ag = (silver_oz["prev"] / TROY_OUNCE_TO_GRAM) * usd_try["prev"]
            if prev_ag > 0:
                gram_gumus_chg = round(((gram_gumus - prev_ag) / prev_ag) * 100, 2)

    def make_sarrafiye(
        code: str,
        name: str,
        PureGoldMultiplier: float,
        weight_info: str,
    ) -> dict:
        if gram_altin is None:
            return {
                "code": code,
                "name": name,
                "category": "Altın Türleri",
                "unit": f"1 Adet ({weight_info})",
                "currency": "TRY",
                "spot_price": None,
                "buy_price": None,
                "sell_price": None,
                "spread_note": "Ücretsiz veri sağlayıcısı alış/satış makası yerine spot referans değer sunar.",
                "change_percent": None,
                "data_available": False,
                "calculation_note": "Spot ons altın veya USD/TRY verisine ulaşılamadığı için hesaplanamadı.",
                "source_name": "Yahoo Finance (GC=F & TRY=X Spot Parite)",
                "source_url": "https://finance.yahoo.com/quote/GC%3DF",
                "is_delayed": True,
                "last_updated": now_iso,
            }

        ref_price = round(gram_altin * PureGoldMultiplier, 2)
        return {
            "code": code,
            "name": name,
            "category": "Altın Türleri",
            "unit": f"1 Adet ({weight_info})",
            "currency": "TRY",
            "spot_price": ref_price,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "Serbest piyasa kuyumcu/banka alış-satış makası içermez; saf altın ağırlığı üzerinden teorik spot referans değeridir.",
            "change_percent": gram_altin_chg,
            "data_available": True,
            "calculation_note": f"24 Ayar Gram Altın × {PureGoldMultiplier} standart darphane has altın katsayısı ile hesaplanmıştır.",
            "source_name": "Yahoo Finance Küresel Spot Altın (GC=F) & USD/TRY (TRY=X)",
            "source_url": "https://finance.yahoo.com/quote/GC%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        }

    assets = [
        {
            "code": "GRAM_ALTIN",
            "name": "Gram Altın (24 Ayar Has)",
            "category": "Altın Türleri",
            "unit": "1 Gram (995/1000 Saflık)",
            "currency": "TRY",
            "spot_price": gram_altin,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "Küresel spot ons altın ve USD/TRY kuru üzerinden hesaplanan referans gram fiyatıdır (alış/satış makası içermez).",
            "change_percent": gram_altin_chg,
            "data_available": gram_altin is not None,
            "calculation_note": "(Ons Altın USD / 31,1034768) × USD/TRY formülüyle anlık pariteden türetilmiştir.",
            "source_name": "Yahoo Finance (GC=F & TRY=X)",
            "source_url": "https://finance.yahoo.com/quote/GC%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        },
        make_sarrafiye(
            "CEYREK_ALTIN",
            "Çeyrek Altın",
            1.6065,
            "1,75 gr 22 Ayar — 1,6065 gr Has Altın",
        ),
        make_sarrafiye(
            "YARIM_ALTIN",
            "Yarım Altın",
            3.213,
            "3,50 gr 22 Ayar — 3,213 gr Has Altın",
        ),
        make_sarrafiye(
            "TAM_ALTIN",
            "Tam Altın (Ziynet)",
            6.426,
            "7,01 gr 22 Ayar — 6,426 gr Has Altın",
        ),
        make_sarrafiye(
            "CUMHURIYET_ALTINI",
            "Cumhuriyet Altını (Ata Lira)",
            6.617,
            "7,216 gr 22 Ayar — 6,617 gr Has Altın",
        ),
        {
            "code": "ONS_ALTIN",
            "name": "Ons Altın (XAU/USD)",
            "category": "Altın Türleri",
            "unit": "1 Troy Ons (31,10 gr)",
            "currency": "USD",
            "spot_price": round(gold_usd, 2) if gold_usd else None,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "Küresel vadeli/spot referans işlem fiyatıdır.",
            "change_percent": gold_oz["change_percent"],
            "data_available": gold_usd is not None,
            "calculation_note": "Doğrudan küresel piyasa (COMEX / GC=F) ons altın verisidir.",
            "source_name": "Yahoo Finance (COMEX Gold GC=F)",
            "source_url": "https://finance.yahoo.com/quote/GC%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        },
        {
            "code": "GRAM_GUMUS",
            "name": "Gümüş (Gram)",
            "category": "Değerli Metaller",
            "unit": "1 Gram (999 Saflık)",
            "currency": "TRY",
            "spot_price": gram_gumus,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "Spot ons gümüş ve USD/TRY kurundan hesaplanan teorik gram gümüş değeridir.",
            "change_percent": gram_gumus_chg,
            "data_available": gram_gumus is not None,
            "calculation_note": "(Ons Gümüş USD / 31,1034768) × USD/TRY formülüyle hesaplanmıştır.",
            "source_name": "Yahoo Finance (SI=F & TRY=X)",
            "source_url": "https://finance.yahoo.com/quote/SI%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        },
        {
            "code": "ONS_GUMUS",
            "name": "Gümüş (Ons - XAG/USD)",
            "category": "Değerli Metaller",
            "unit": "1 Troy Ons (31,10 gr)",
            "currency": "USD",
            "spot_price": round(silver_usd, 2) if silver_usd else None,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "Küresel spot/vadeli gümüş referans fiyatıdır.",
            "change_percent": silver_oz["change_percent"],
            "data_available": silver_usd is not None,
            "calculation_note": "Doğrudan küresel piyasa (SI=F) ons gümüş verisidir.",
            "source_name": "Yahoo Finance (COMEX Silver SI=F)",
            "source_url": "https://finance.yahoo.com/quote/SI%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        },
        {
            "code": "BRONZ",
            "name": "Bronz (Tunç Alaşımı)",
            "category": "Endüstriyel Metaller ve Alaşımlar",
            "unit": "Standart Spot Borsa Birimi Bulunmamaktadır",
            "currency": "USD / TRY",
            "spot_price": None,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "Ücretsiz açık borsa kaynaklarında standart spot Bronz kodu yer almamaktadır.",
            "change_percent": None,
            "data_available": False,
            "calculation_note": (
                "Bronz (~%88 Bakır + %12 Kalay alaşımı), altın veya gümüş gibi küresel finans "
                "borsalarında tekil bir standart spot kodla işlem görmez. Proje dokümanı Bölüm 3.5 "
                "('Bir değer ücretsiz kaynaklardan elde edilemiyorsa uydurulmamalı; veri bulunamadığı "
                "belirtilmelidir') ilkesi gereği tahmini fiyat uydurulmamıştır. Referans için ana "
                "bileşeni olan Bakır (HG=F) fiyatı aşağıda paylaşılmıştır."
            ),
            "source_name": "Veri Kaynağı Doğrulama Notu (Bölüm 3.5)",
            "source_url": "https://finance.yahoo.com/quote/HG%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        },
        {
            "code": "BAKIR_REF",
            "name": "Bakır (Bronz Ana Bileşeni Referansı - HG=F)",
            "category": "Endüstriyel Metaller ve Alaşımlar",
            "unit": "1 Pound (lb ≈ 0,4536 kg)",
            "currency": "USD",
            "spot_price": round(copper_usd, 4) if copper_usd else None,
            "buy_price": None,
            "sell_price": None,
            "spread_note": "COMEX küresel endüstriyel bakır vadeli işlem referans fiyatıdır.",
            "change_percent": copper_lb["change_percent"],
            "data_available": copper_usd is not None,
            "calculation_note": "Bronz alaşımının ~%88'ini oluşturan saf bakırın küresel borsa (HG=F) birim fiyatıdır.",
            "source_name": "Yahoo Finance (COMEX Copper HG=F)",
            "source_url": "https://finance.yahoo.com/quote/HG%3DF",
            "is_delayed": True,
            "last_updated": now_iso,
        },
    ]

    result = {
        "fx_reference": {
            "pair": "USD/TRY",
            "rate": round(fx_rate, 4) if fx_rate else None,
            "change_percent": usd_try["change_percent"],
            "source_name": "Yahoo Finance (TRY=X)",
            "source_url": "https://finance.yahoo.com/quote/TRY%3DX",
        },
        "assets": assets,
        "source_name": "Yahoo Finance Küresel Emtia & Döviz Verileri (Gecikmeli)",
        "is_delayed": True,
        "last_updated": now_iso,
        "disclaimer": (
            "Altın türleri ve gümüş fiyatları küresel ons fiyatları ile USD/TRY kuru üzerinden "
            "standart darphane has ağırlık katsayılarıyla hesaplanan bilgilendirme amaçlı "
            "referans değerlerdir; kuyumcu veya banka gişe alış/satış makaslarını içermez."
        ),
    }
    cache.set(cache_key, result, timeout=300)
    return result
