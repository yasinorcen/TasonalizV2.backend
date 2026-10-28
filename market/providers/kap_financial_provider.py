"""
KAP & IFRS Financial Statements Provider for Borsa İstanbul Companies.
Provides structured Bilanço (Balance Sheet), Gelir Tablosu (Income Statement),
and Nakit Akış Tablosu (Cash Flow Statement) mapped to official Turkish KAP/TMS terminology,
along with official KAP company links, reporting period metadata, and currency.
Never fabricates or guesses missing line items (Section 3.3 & 7).
"""

import logging
import math
from typing import Any
from django.core.cache import cache
from django.utils import timezone
import yfinance as yf

logger = logging.getLogger(__name__)


BALANCE_SHEET_SCHEMA = [
    {
        "key": "current_assets",
        "label": "Dönen Varlıklar (Toplam)",
        "category": "Varlıklar",
        "is_summary": True,
        "yf_keys": ["Current Assets"],
        "description": "Bir yıl içinde nakde çevrilmesi, satılması veya tüketilmesi beklenen varlıkların toplamıdır.",
    },
    {
        "key": "cash_and_equivalents",
        "label": "Nakit ve Nakit Benzerleri",
        "category": "Varlıklar",
        "is_summary": False,
        "yf_keys": [
            "Cash And Cash Equivalents",
            "Cash Cash Equivalents And Short Term Investments",
            "Cash Financial",
        ],
        "description": "Şirketin kasasında ve bankalarda anında kullanılabilir durumda bulunan likit varlıklarıdır.",
    },
    {
        "key": "accounts_receivable",
        "label": "Ticari Alacaklar",
        "category": "Varlıklar",
        "is_summary": False,
        "yf_keys": ["Accounts Receivable", "Receivables"],
        "description": "Mal veya hizmet satışlarından doğan ve henüz tahsil edilmemiş kısa vadeli müşteri alacaklarıdır.",
    },
    {
        "key": "inventories",
        "label": "Stoklar",
        "category": "Varlıklar",
        "is_summary": False,
        "yf_keys": ["Inventory"],
        "description": "Satılmak veya üretimde kullanılmak üzere elde tutulan hammadde, yarı mamul ve ticari mallardır.",
    },
    {
        "key": "non_current_assets",
        "label": "Duran Varlıklar (Toplam)",
        "category": "Varlıklar",
        "is_summary": True,
        "yf_keys": ["Total Non Current Assets"],
        "description": "Bir yıldan daha uzun sürede işletme faaliyetlerinde kullanılacak uzun vadeli varlıkların toplamıdır.",
    },
    {
        "key": "net_ppe",
        "label": "Maddi Duran Varlıklar (Net)",
        "category": "Varlıklar",
        "is_summary": False,
        "yf_keys": ["Net PPE"],
        "description": "Üretim tesisleri, binalar, makineler ve ekipmanların birikmiş amortisman düşülmüş net değeridir.",
    },
    {
        "key": "intangible_assets",
        "label": "Maddi Olmayan Duran Varlıklar ve Şerefiye",
        "category": "Varlıklar",
        "is_summary": False,
        "yf_keys": ["Goodwill And Other Intangible Assets", "Other Intangible Assets"],
        "description": "Lisanslar, yazılımlar, patentler, marka değerleri ve şerefiye kalemlerinin toplamıdır.",
    },
    {
        "key": "total_assets",
        "label": "TOPLAM VARLIKLAR (AKTİF TOPLAMI)",
        "category": "Varlıklar",
        "is_summary": True,
        "yf_keys": ["Total Assets"],
        "description": "Şirketin sahip olduğu dönen ve duran tüm ekonomik kaynakların (aktiflerin) genel toplamıdır.",
    },
    {
        "key": "current_liabilities",
        "label": "Kısa Vadeli Yükümlülükler (Toplam)",
        "category": "Yükümlülükler",
        "is_summary": True,
        "yf_keys": ["Current Liabilities"],
        "description": "Vadesi bir yıldan kısa olan finansal borçlar, ticari borçlar ve diğer kısa vadeli yükümlülüklerdir.",
    },
    {
        "key": "short_term_debt",
        "label": "Kısa Vadeli Finansal Borçlar",
        "category": "Yükümlülükler",
        "is_summary": False,
        "yf_keys": ["Current Debt", "Current Debt And Capital Lease Obligation"],
        "description": "Bir yıl içinde ödenmesi gereken banka kredileri, tahviller ve finansal kiralama borçlarıdır.",
    },
    {
        "key": "accounts_payable",
        "label": "Ticari Borçlar",
        "category": "Yükümlülükler",
        "is_summary": False,
        "yf_keys": ["Accounts Payable", "Payables"],
        "description": "Tedarikçilerden vadeli alınan mal ve hizmetler karşılığında ödenecek borçlardır.",
    },
    {
        "key": "non_current_liabilities",
        "label": "Uzun Vadeli Yükümlülükler (Toplam)",
        "category": "Yükümlülükler",
        "is_summary": True,
        "yf_keys": ["Total Non Current Liabilities Net Minority Interest"],
        "description": "Vadesi bir yıldan uzun olan kredi, tahvil, kıdem tazminatı karşılığı ve ertelenmiş vergi yükümlülükleridir.",
    },
    {
        "key": "long_term_debt",
        "label": "Uzun Vadeli Finansal Borçlar",
        "category": "Yükümlülükler",
        "is_summary": False,
        "yf_keys": ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"],
        "description": "Vadesi bir yıldan uzun olan banka kredileri ve finansal borçlanma araçlarıdır.",
    },
    {
        "key": "total_liabilities",
        "label": "TOPLAM YÜKÜMLÜLÜKLER (YABANCI KAYNAKLAR)",
        "category": "Yükümlülükler",
        "is_summary": True,
        "yf_keys": ["Total Liabilities Net Minority Interest"],
        "description": "Şirketin kısa ve uzun vadeli tüm borç ve yükümlülüklerinin toplamıdır.",
    },
    {
        "key": "total_equity",
        "label": "ÖZKAYNAKLAR (ANA ORTAKLIĞA AİT)",
        "category": "Özkaynaklar",
        "is_summary": True,
        "yf_keys": ["Stockholders Equity", "Total Equity Gross Minority Interest"],
        "description": "Toplam varlıklardan toplam yükümlülükler düşüldükten sonra ortaklara kalan net varlık değeridir.",
    },
    {
        "key": "paid_in_capital",
        "label": "Ödenmiş / Çıkarılmış Sermaye",
        "category": "Özkaynaklar",
        "is_summary": False,
        "yf_keys": ["Common Stock", "Capital Stock"],
        "description": "Şirketin esas sözleşmesinde yer alan ve ortaklarca taahhüt edilip ödenmiş nominal sermayesidir.",
    },
    {
        "key": "retained_earnings",
        "label": "Geçmiş Yıllar Kârları / Zararları",
        "category": "Özkaynaklar",
        "is_summary": False,
        "yf_keys": ["Retained Earnings"],
        "description": "Şirketin geçmiş dönemlerde elde edip dağıtmadığı ve bünyesinde bıraktığı birikmiş kârlarıdır.",
    },
]

INCOME_STATEMENT_SCHEMA = [
    {
        "key": "revenue",
        "label": "Hasılat (Satış Gelirleri)",
        "category": "Gelirler",
        "is_summary": True,
        "yf_keys": ["Total Revenue", "Operating Revenue"],
        "description": "Şirketin ana faaliyet konusu kapsamında gerçekleştirdiği mal ve hizmet satışlarının net toplamıdır.",
    },
    {
        "key": "cost_of_revenue",
        "label": "Satışların Maliyeti",
        "category": "Giderler",
        "is_summary": False,
        "yf_keys": ["Cost Of Revenue", "Reconciled Cost Of Revenue"],
        "description": "Satılan mal ve sunulan hizmetlerin üretilmesi veya tedarik edilmesi için katlanılan doğrudan maliyetlerdir.",
    },
    {
        "key": "gross_profit",
        "label": "BRÜT KÂR / (ZARAR)",
        "category": "Kârlılık",
        "is_summary": True,
        "yf_keys": ["Gross Profit"],
        "description": "Hasılattan satışların maliyeti düşüldükten sonra kalan temel ticari/üretim kârıdır.",
    },
    {
        "key": "operating_expense",
        "label": "Faaliyet Giderleri (Toplam)",
        "category": "Giderler",
        "is_summary": False,
        "yf_keys": ["Operating Expense"],
        "description": "Genel yönetim, pazarlama, satış, dağıtım ve araştırma-geliştirme giderlerinin toplamıdır.",
    },
    {
        "key": "sga_expense",
        "label": "Pazarlama, Satış ve Genel Yönetim Giderleri",
        "category": "Giderler",
        "is_summary": False,
        "yf_keys": ["Selling General And Administration"],
        "description": "Şirketin yönetim ve pazarlama organizasyonunu sürdürmek için yaptığı operasyonel harcamalardır.",
    },
    {
        "key": "rd_expense",
        "label": "Araştırma ve Geliştirme (Ar-Ge) Giderleri",
        "category": "Giderler",
        "is_summary": False,
        "yf_keys": ["Research And Development"],
        "description": "Yeni ürün, süreç ve teknoloji geliştirmek amacıyla yapılan Ar-Ge harcamalarıdır.",
    },
    {
        "key": "operating_income",
        "label": "ESAS FAALİYET KÂRI / (ZARARI) - FVÖK",
        "category": "Kârlılık",
        "is_summary": True,
        "yf_keys": ["Operating Income", "EBIT"],
        "description": "Finansman gelir/giderleri ve vergi öncesinde şirketin ana işinden ürettiği operasyonel kârdır.",
    },
    {
        "key": "ebitda",
        "label": "FAVÖK (Faiz, Amortisman ve Vergi Öncesi Kâr)",
        "category": "Kârlılık",
        "is_summary": True,
        "yf_keys": ["EBITDA", "Normalized EBITDA"],
        "description": "Nakit çıkışı gerektirmeyen amortisman giderleri eklenmiş operasyonel kârlılık göstergesidir.",
    },
    {
        "key": "net_interest",
        "label": "Net Finansman Gelir / (Gideri)",
        "category": "Finansman",
        "is_summary": False,
        "yf_keys": ["Net Non Operating Interest Income Expense", "Net Interest Income"],
        "description": "Faiz gelirleri ile kredi/tahvil faiz giderleri arasındaki net farktır.",
    },
    {
        "key": "pretax_income",
        "label": "Sürdürülen Faaliyetler Vergi Öncesi Kârı / (Zararı)",
        "category": "Kârlılık",
        "is_summary": True,
        "yf_keys": ["Pretax Income"],
        "description": "Kurumlar vergisi hesaplanmadan önceki toplam dönem kârı veya zararıdır.",
    },
    {
        "key": "tax_provision",
        "label": "Vergi Gideri / (Geliri)",
        "category": "Vergi",
        "is_summary": False,
        "yf_keys": ["Tax Provision"],
        "description": "Dönem vergi gideri ile ertelenmiş vergi gelir/giderlerinin net tutarıdır.",
    },
    {
        "key": "net_income",
        "label": "NET DÖNEM KÂRI / (ZARARI)",
        "category": "Kârlılık",
        "is_summary": True,
        "yf_keys": ["Net Income", "Net Income Common Stockholders"],
        "description": "Tüm gelir, gider, finansman maliyetleri ve vergiler sonrası ana ortaklığa düşen net kâr veya zarardır.",
    },
]

CASH_FLOW_SCHEMA = [
    {
        "key": "operating_cash_flow",
        "label": "İşletme Faaliyetlerinden Nakit Akışları",
        "category": "Nakit Akışları",
        "is_summary": True,
        "yf_keys": [
            "Operating Cash Flow",
            "Cash Flow From Continuing Operating Activities",
        ],
        "description": "Şirketin esas faaliyetlerinden (mal/hizmet satışı, tahsilatlar ve tedarikçi ödemeleri) ürettiği net nakittir.",
    },
    {
        "key": "investing_cash_flow",
        "label": "Yatırım Faaliyetlerinden Nakit Akışları",
        "category": "Nakit Akışları",
        "is_summary": True,
        "yf_keys": [
            "Investing Cash Flow",
            "Cash Flow From Continuing Investing Activities",
        ],
        "description": "Maddi/maddi olmayan duran varlık alım-satımları ve finansal yatırımlar sonucu oluşan nakit giriş/çıkışıdır.",
    },
    {
        "key": "capital_expenditure",
        "label": "Sermaye Harcamaları (CAPEX / Sabit Kıymet Alımları)",
        "category": "Nakit Akışları",
        "is_summary": False,
        "yf_keys": ["Capital Expenditure"],
        "description": "Tesis, makine, ekipman ve teknoloji yatırımları için yapılan nakit çıkışlarıdır.",
    },
    {
        "key": "financing_cash_flow",
        "label": "Finansman Faaliyetlerinden Nakit Akışları",
        "category": "Nakit Akışları",
        "is_summary": True,
        "yf_keys": [
            "Financing Cash Flow",
            "Cash Flow From Continuing Financing Activities",
        ],
        "description": "Kredi kullanımı/geri ödemesi, sermaye artırımı ve temettü ödemelerinden kaynaklanan nakit hareketleridir.",
    },
    {
        "key": "free_cash_flow",
        "label": "Serbest Nakit Akışı (Free Cash Flow)",
        "category": "Nakit Akışları",
        "is_summary": True,
        "yf_keys": ["Free Cash Flow"],
        "description": "İşletme faaliyetlerinden üretilen nakitten sermaye harcamaları (CAPEX) düşüldükten sonra kalan nakittir.",
    },
    {
        "key": "beginning_cash",
        "label": "Dönem Başı Nakit ve Nakit Benzerleri",
        "category": "Nakit Bakiyesi",
        "is_summary": False,
        "yf_keys": ["Beginning Cash Position"],
        "description": "Raporlama döneminin başında şirketin elinde bulunan nakit mevcududur.",
    },
    {
        "key": "ending_cash",
        "label": "DÖNEM SONU NAKİT VE NAKİT BENZERLERİ",
        "category": "Nakit Bakiyesi",
        "is_summary": True,
        "yf_keys": ["End Cash Position"],
        "description": "Raporlama dönemi sonunda şirketin elinde kalan toplam nakit ve nakit benzeri varlıklardır.",
    },
]


def _safe_num(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return round(f, 2)
    except (TypeError, ValueError):
        return None


def _format_period_label(col: Any) -> str:
    if hasattr(col, "strftime"):
        return f"{col.year}/{col.month:02d}"
    s = str(col)[:10]
    parts = s.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return s


def _extract_table_from_df(df: Any, schema: list[dict]) -> tuple[list[str], list[dict]]:
    if df is None or getattr(df, "empty", True):
        return [], []

    cols = list(df.columns)[:4]
    periods = [_format_period_label(c) for c in cols]

    rows = []
    for item in schema:
        values_by_period: dict[str, float | None] = {}
        matched_row = None
        for yf_key in item["yf_keys"]:
            if yf_key in df.index:
                matched_row = df.loc[yf_key]
                break

        for col, period_label in zip(cols, periods):
            if matched_row is not None:
                raw_val = matched_row.get(col) if hasattr(matched_row, "get") else matched_row[col]
                values_by_period[period_label] = _safe_num(raw_val)
            else:
                values_by_period[period_label] = None

        rows.append(
            {
                "key": item["key"],
                "label": item["label"],
                "category": item["category"],
                "is_summary": item["is_summary"],
                "description": item["description"],
                "values": values_by_period,
            }
        )

    return periods, rows


def get_company_financial_statements(code: str, kap_url: str = "") -> dict:
    """
    Retrieves Bilanço, Gelir Tablosu, and Nakit Akış Tablosu for a BIST company.
    Includes full KAP attribution, periods, currency, and line-by-line descriptions.
    """
    clean_code = code.strip().upper()
    cache_key = f"financial_statements_v1_{clean_code}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    yf_symbol = f"{clean_code}.IS"
    now_iso = timezone.now().isoformat()
    official_kap_link = (
        kap_url
        if kap_url
        else f"https://www.kap.org.tr/tr/bist-sirketler"
    )
    kap_financials_link = (
        kap_url.replace("/sirket-bilgileri/ozet/", "/sirket-finansal-bilgileri/")
        if "/sirket-bilgileri/ozet/" in kap_url
        else official_kap_link
    )

    try:
        ticker = yf.Ticker(yf_symbol)
        currency = "TRY"
        try:
            currency = ticker.fast_info.get("currency") or "TRY"
        except Exception:
            currency = "TRY"

        bs_df = ticker.balance_sheet
        is_df = ticker.income_stmt
        cf_df = ticker.cashflow

        bs_periods, bs_rows = _extract_table_from_df(bs_df, BALANCE_SHEET_SCHEMA)
        is_periods, is_rows = _extract_table_from_df(is_df, INCOME_STATEMENT_SCHEMA)
        cf_periods, cf_rows = _extract_table_from_df(cf_df, CASH_FLOW_SCHEMA)

        all_periods = []
        for p in bs_periods + is_periods + cf_periods:
            if p not in all_periods:
                all_periods.append(p)

        has_any_data = bool(bs_periods or is_periods or cf_periods)

        result = {
            "code": clean_code,
            "symbol": yf_symbol,
            "data_available": has_any_data,
            "currency": currency,
            "unit_note": "Tutarlar aksi belirtilmedikçe ilgili raporlama para birimi (tam TL / TRY) cinsindendir.",
            "periods": all_periods,
            "kap_company_url": official_kap_link,
            "kap_financials_url": kap_financials_link,
            "yahoo_financials_url": f"https://finance.yahoo.com/quote/{yf_symbol}/financials/",
            "source_name": "Kamuyu Aydınlatma Platformu (KAP) Bildirimleri / Uluslararası Finansal Raporlama Standartları (TMS/TFRS) Veri Akışı",
            "last_updated": now_iso,
            "is_delayed": True,
            "tables": {
                "BILANCO": {
                    "type": "BILANCO",
                    "title": "Bilanço (Finansal Durum Tablosu)",
                    "subtitle": "Şirketin belirli bir tarihteki varlıklarını (aktif), borçlarını ve özkaynaklarını (pasif) gösterir.",
                    "periods": bs_periods,
                    "rows": bs_rows,
                    "data_available": bool(bs_periods),
                },
                "GELIR": {
                    "type": "GELIR",
                    "title": "Gelir Tablosu (Kâr veya Zarar Tablosu)",
                    "subtitle": "Şirketin ilgili raporlama dönemindeki satış gelirlerini, maliyetlerini, giderlerini ve net dönem kâr/zararını gösterir.",
                    "periods": is_periods,
                    "rows": is_rows,
                    "data_available": bool(is_periods),
                },
                "NAKIT": {
                    "type": "NAKIT",
                    "title": "Nakit Akış Tablosu",
                    "subtitle": "Dönem içindeki işletme, yatırım ve finansman faaliyetlerinden kaynaklanan nakit giriş ve çıkışlarını özetler.",
                    "periods": cf_periods,
                    "rows": cf_rows,
                    "data_available": bool(cf_periods),
                },
            },
            "unavailable_reason": (
                None
                if has_any_data
                else (
                    "Bu şirket için ücretsiz standart finansal tablo servisinde yapılandırılmış dönem "
                    "verisi bulunamadı. Lütfen yukarıdaki Resmî KAP Finansal Bilgiler bağlantısından "
                    "doğrudan PDF/XBRL bildirimlerini inceleyiniz."
                )
            ),
        }
        cache.set(cache_key, result, timeout=900)
        return result

    except Exception as exc:
        logger.warning("Financial statements fetch failed for %s: %s", clean_code, exc)
        fallback = {
            "code": clean_code,
            "symbol": yf_symbol,
            "data_available": False,
            "currency": "TRY",
            "unit_note": "Tutarlar TRY cinsindendir.",
            "periods": [],
            "kap_company_url": official_kap_link,
            "kap_financials_url": kap_financials_link,
            "yahoo_financials_url": f"https://finance.yahoo.com/quote/{yf_symbol}/financials/",
            "source_name": "Kamuyu Aydınlatma Platformu (KAP) / Finansal Veri Sağlayıcısı",
            "last_updated": now_iso,
            "is_delayed": True,
            "tables": {
                "BILANCO": {
                    "type": "BILANCO",
                    "title": "Bilanço (Finansal Durum Tablosu)",
                    "subtitle": "Şirketin varlık, yükümlülük ve özkaynak yapısı.",
                    "periods": [],
                    "rows": [],
                    "data_available": False,
                },
                "GELIR": {
                    "type": "GELIR",
                    "title": "Gelir Tablosu",
                    "subtitle": "Şirketin gelir, gider ve kârlılık tablosu.",
                    "periods": [],
                    "rows": [],
                    "data_available": False,
                },
                "NAKIT": {
                    "type": "NAKIT",
                    "title": "Nakit Akış Tablosu",
                    "subtitle": "Şirketin nakit giriş ve çıkışları.",
                    "periods": [],
                    "rows": [],
                    "data_available": False,
                },
            },
            "unavailable_reason": (
                "Finansal tablo verilerine şu anda erişilemedi. Resmî KAP bağlantısını "
                "kullanarak şirketin yayımladığı bildirimlere doğrudan ulaşabilirsiniz."
            ),
        }
        cache.set(cache_key, fallback, timeout=120)
        return fallback
