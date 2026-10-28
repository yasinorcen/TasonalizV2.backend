"""
Stock Price & Market Quote Provider for Borsa İstanbul (BIST) equities.
Uses Yahoo Finance (.IS suffix) with Django LocMemCache to provide delayed market data,
price history for charts, and explicit provenance metadata (Section 3.1 & 7).
Never fabricates prices if the upstream provider has no data for a ticker.
"""

import logging
import math
from typing import Any
from django.core.cache import cache
from django.utils import timezone
import yfinance as yf

logger = logging.getLogger(__name__)


def _clean_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def _clean_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None


def get_stock_quote_and_history(code: str, period: str = "6mo") -> dict:
    """
    Fetches delayed stock quote and historical closing prices for {code}.IS.
    """
    clean_code = code.strip().upper()
    cache_key = f"stock_quote_{clean_code}_{period}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    yf_symbol = f"{clean_code}.IS"
    source_url = f"https://finance.yahoo.com/quote/{yf_symbol}"
    now_iso = timezone.now().isoformat()

    try:
        ticker = yf.Ticker(yf_symbol)
        fast = ticker.fast_info

        last_price = _clean_float(fast.get("lastPrice"))
        prev_close = _clean_float(fast.get("previousClose") or fast.get("regularMarketPreviousClose"))
        day_high = _clean_float(fast.get("dayHigh"))
        day_low = _clean_float(fast.get("dayLow"))
        open_price = _clean_float(fast.get("open"))
        volume = _clean_int(fast.get("lastVolume"))
        market_cap = _clean_int(fast.get("marketCap"))
        year_high = _clean_float(fast.get("yearHigh"))
        year_low = _clean_float(fast.get("yearLow"))
        ma50 = _clean_float(fast.get("fiftyDayAverage"))
        ma200 = _clean_float(fast.get("twoHundredDayAverage"))
        currency = fast.get("currency") or "TRY"

        change = None
        change_percent = None
        if last_price is not None and prev_close and prev_close > 0:
            change = round(last_price - prev_close, 2)
            change_percent = round(((last_price - prev_close) / prev_close) * 100, 2)

        history_points = []
        try:
            hist_df = ticker.history(period=period, interval="1d")
            if hist_df is not None and not hist_df.empty:
                for idx, row in hist_df.tail(120).iterrows():
                    close_val = _clean_float(row.get("Close"))
                    vol_val = _clean_int(row.get("Volume"))
                    if close_val is not None:
                        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                        history_points.append(
                            {
                                "date": date_str,
                                "close": close_val,
                                "volume": vol_val,
                            }
                        )
        except Exception as hist_exc:
            logger.warning("History fetch error for %s: %s", yf_symbol, hist_exc)

        data_available = last_price is not None
        result = {
            "code": clean_code,
            "symbol": yf_symbol,
            "data_available": data_available,
            "currency": currency,
            "last_price": last_price,
            "previous_close": prev_close,
            "change": change,
            "change_percent": change_percent,
            "open": open_price,
            "day_high": day_high,
            "day_low": day_low,
            "volume": volume,
            "market_cap": market_cap,
            "year_high": year_high,
            "year_low": year_low,
            "ma50": ma50,
            "ma200": ma200,
            "history": history_points,
            "source_name": "Yahoo Finance (BIST 15 Dk Gecikmeli / Gün Sonu Piyasa Verisi)",
            "source_url": source_url,
            "is_delayed": True,
            "delay_disclaimer": (
                "Hisse fiyatı verileri gerçek zamanlı değildir; ücretsiz veri sağlayıcısı "
                "üzerinden約 15 dakika gecikmeli veya son işlem günü kapanışı olarak sunulmaktadır."
            ),
            "last_updated": now_iso,
            "unavailable_reason": (
                None
                if data_available
                else "Ücretsiz veri sağlayıcısında bu hisse kodu için güncel fiyat verisi bulunamadı."
            ),
        }
        cache.set(cache_key, result, timeout=300)
        return result

    except Exception as exc:
        logger.warning("Failed to fetch stock quote for %s: %s", yf_symbol, exc)
        fallback = {
            "code": clean_code,
            "symbol": yf_symbol,
            "data_available": False,
            "currency": "TRY",
            "last_price": None,
            "previous_close": None,
            "change": None,
            "change_percent": None,
            "open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "market_cap": None,
            "year_high": None,
            "year_low": None,
            "ma50": None,
            "ma200": None,
            "history": [],
            "source_name": "Yahoo Finance (BIST Gecikmeli Veri)",
            "source_url": source_url,
            "is_delayed": True,
            "delay_disclaimer": (
                "Hisse fiyatı verileri gerçek zamanlı değildir; ücretsiz veri sağlayıcısının "
                "sunduğu güncellik kapsamında gösterilmektedir."
            ),
            "last_updated": now_iso,
            "unavailable_reason": "Veri sağlayıcısına şu anda erişilemedi veya bu hisse için fiyat verisi bulunamadı.",
        }
        cache.set(cache_key, fallback, timeout=60)
        return fallback


def get_featured_market_summary(codes: list[str] | None = None) -> dict:
    """
    Fetches a quick snapshot of featured BIST companies and BIST 100 index (XU100.IS)
    for the homepage overview.
    """
    cache_key = "featured_market_summary_v1"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    target_codes = codes or [
        "THYAO", "ASELS", "GARAN", "EREGL", "TUPRS", "KCHOL", "BIMAS", "SISE"
    ]
    now_iso = timezone.now().isoformat()

    # Fetch BIST 100 Index (XU100.IS)
    bist100_info = {
        "symbol": "XU100",
        "name": "BIST 100 Endeksi",
        "last_price": None,
        "change": None,
        "change_percent": None,
        "data_available": False,
        "source_name": "Yahoo Finance (XU100.IS)",
        "source_url": "https://finance.yahoo.com/quote/XU100.IS",
        "is_delayed": True,
        "last_updated": now_iso,
    }
    try:
        idx_fast = yf.Ticker("XU100.IS").fast_info
        lp = _clean_float(idx_fast.get("lastPrice"))
        pc = _clean_float(idx_fast.get("previousClose") or idx_fast.get("regularMarketPreviousClose"))
        if lp is not None:
            bist100_info["last_price"] = lp
            bist100_info["data_available"] = True
            if pc and pc > 0:
                bist100_info["change"] = round(lp - pc, 2)
                bist100_info["change_percent"] = round(((lp - pc) / pc) * 100, 2)
    except Exception as exc:
        logger.warning("BIST 100 index fetch error: %s", exc)

    stocks = []
    for code in target_codes:
        quote = get_stock_quote_and_history(code, period="1mo")
        stocks.append(
            {
                "code": quote["code"],
                "last_price": quote["last_price"],
                "change": quote["change"],
                "change_percent": quote["change_percent"],
                "volume": quote["volume"],
                "market_cap": quote["market_cap"],
                "currency": quote["currency"],
                "data_available": quote["data_available"],
                "is_delayed": True,
                "last_updated": quote["last_updated"],
            }
        )

    payload = {
        "bist100": bist100_info,
        "featured_quotes": stocks,
        "source_name": "Yahoo Finance (BIST Gecikmeli Piyasa Verisi)",
        "is_delayed": True,
        "last_updated": now_iso,
    }
    cache.set(cache_key, payload, timeout=300)
    return payload
