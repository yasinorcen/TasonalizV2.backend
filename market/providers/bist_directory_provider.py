"""
Official KAP Borsa İstanbul (BIST) Company Directory Provider.
Fetches the complete BIST company list from https://www.kap.org.tr/tr/bist-sirketler
and syncs them into the Company database model. Includes a reliable fallback list
of core BIST companies so offline or rate-limited environments remain functional.
"""

from collections import defaultdict
import logging
import re
import requests
from bs4 import BeautifulSoup
from django.utils import timezone

from market.models import Company

logger = logging.getLogger(__name__)

KAP_BIST_COMPANIES_URL = "https://www.kap.org.tr/tr/bist-sirketler"
KAP_BASE_URL = "https://www.kap.org.tr"

BIST30_CODES = {
    "AKBNK", "ALARK", "ARCLK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "CIMSA",
    "DOAS", "EKGYO", "ENKAI", "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS",
    "ISCTR", "KCHOL", "KONTR", "KOZAL", "KRDMD", "MGROS", "OYAKC", "PETKM",
    "PGSUS", "SAHOL", "SASA", "SISE", "TCELL", "THYAO", "TOASO", "TTKOM",
    "TUPRS", "ULKER", "VAKBN", "YKBNK",
}

FALLBACK_BIST_COMPANIES = [
    ("ACSEL", "ACISELSAN ACIPAYAM SELÜLOZ SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/1626-aciselsan-acipayam-seluloz-sanayi-ve-ticaret-a-s"),
    ("ADEL", "ADEL KALEMCİLİK TİCARET VE SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/832-adel-kalemcilik-ticaret-ve-sanayi-a-s"),
    ("AEFES", "ANADOLU EFES BİRACILIK VE MALT SANAYİİ A.Ş.", "/tr/sirket-bilgileri/ozet/848-anadolu-efes-biracilik-ve-malt-sanayii-a-s"),
    ("AGHOL", "AG ANADOLU GRUBU HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/1131-ag-anadolu-grubu-holding-a-s"),
    ("AKBNK", "AKBANK T.A.Ş.", "/tr/sirket-bilgileri/ozet/2412-akbank-t-a-s"),
    ("AKSA", "AKSA AKRİLİK KİMYA SANAYİİ A.Ş.", "/tr/sirket-bilgileri/ozet/840-aksa-akrilik-kimya-sanayii-a-s"),
    ("AKSEN", "AKSA ENERJİ ÜRETİM A.Ş.", "/tr/sirket-bilgileri/ozet/1439-aksa-enerji-uretim-a-s"),
    ("ALARK", "ALARKO HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/842-alarko-holding-a-s"),
    ("ARCLK", "ARÇELİK A.Ş.", "/tr/sirket-bilgileri/ozet/853-arcelik-a-s"),
    ("ASELS", "ASELSAN ELEKTRONİK SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/856-aselsan-elektronik-sanayi-ve-ticaret-a-s"),
    ("ASTOR", "ASTOR ENERJİ A.Ş.", "/tr/sirket-bilgileri/ozet/5387-astor-enerji-a-s"),
    ("BIMAS", "BİM BİRLEŞİK MAĞAZALAR A.Ş.", "/tr/sirket-bilgileri/ozet/868-bim-birlesik-magazalar-a-s"),
    ("BRSAN", "BORUSAN BİRLEŞİK BORU FABRİKALARI SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/874-borusan-birlesik-boru-fabrikalari-sanayi-ve-ticaret-a-s"),
    ("CCOLA", "COCA-COLA İÇECEK A.Ş.", "/tr/sirket-bilgileri/ozet/883-coca-cola-icecek-a-s"),
    ("CIMSA", "ÇİMSA ÇİMENTO SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/889-cimsa-cimento-sanayi-ve-ticaret-a-s"),
    ("CWENE", "CW ENERJİ MÜHENDİSLİK TİCARET VE SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/5502-cw-enerji-muhendislik-ticaret-ve-sanayi-a-s"),
    ("DOAS", "DOĞUŞ OTOMOTİV SERVİS VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/911-dogus-otomotiv-servis-ve-ticaret-a-s"),
    ("DOHOL", "DOĞAN ŞİRKETLER GRUBU HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/910-dogan-sirketler-grubu-holding-a-s"),
    ("ECILC", "EİS ECZACIBAŞI İLAÇ, SINAİ VE FİNANSAL YATIRIMLAR SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/917-eis-eczacibasi-ilac-sinai-ve-finansal-yatirimlar-sanayi-ve-ticaret-a-s"),
    ("EKGYO", "EMLAK KONUT GAYRİMENKUL YATIRIM ORTAKLIĞI A.Ş.", "/tr/sirket-bilgileri/ozet/1496-emlak-konut-gayrimenkul-yatirim-ortakligi-a-s"),
    ("ENJSA", "ENERJİSA ENERJİ A.Ş.", "/tr/sirket-bilgileri/ozet/4040-enerjisa-enerji-a-s"),
    ("ENKAI", "ENKA İNŞAAT VE SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/923-enka-insaat-ve-sanayi-a-s"),
    ("EREGL", "EREĞLİ DEMİR VE ÇELİK FABRİKALARI T.A.Ş.", "/tr/sirket-bilgileri/ozet/924-eregli-demir-ve-celik-fabrikalari-t-a-s"),
    ("EUPWR", "EUROPOWER ENERJİ VE OTOMASYON TEKNOLOJİLERİ SANAYİ TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/5500-europower-enerji-ve-otomasyon-teknolojileri-sanayi-ticaret-a-s"),
    ("FROTO", "FORD OTOMOTİV SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/932-ford-otomotiv-sanayi-a-s"),
    ("GARAN", "TÜRKİYE GARANTİ BANKASI A.Ş.", "/tr/sirket-bilgileri/ozet/2424-turkiye-garanti-bankasi-a-s"),
    ("GESAN", "GİRİŞİM ELEKTRİK SANAYİ TAAHHÜT VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/4875-girisim-elektrik-sanayi-taahhut-ve-ticaret-a-s"),
    ("GUBRF", "GÜBRE FABRİKALARI T.A.Ş.", "/tr/sirket-bilgileri/ozet/943-gubre-fabrikalari-t-a-s"),
    ("HALKB", "TÜRKİYE HALK BANKASI A.Ş.", "/tr/sirket-bilgileri/ozet/2425-turkiye-halk-bankasi-a-s"),
    ("HEKTS", "HEKTAŞ TİCARET T.A.Ş.", "/tr/sirket-bilgileri/ozet/947-hektas-ticaret-t-a-s"),
    ("ISCTR", "TÜRKİYE İŞ BANKASI A.Ş.", "/tr/sirket-bilgileri/ozet/2428-turkiye-is-bankasi-a-s"),
    ("ISMEN", "İŞ YATIRIM MENKUL DEĞERLER A.Ş.", "/tr/sirket-bilgileri/ozet/1184-is-yatirim-menkul-degerler-a-s"),
    ("KCHOL", "KOÇ HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/985-koc-holding-a-s"),
    ("KONTR", "KONTROLMATİK TEKNOLOJİ ENERJİ VE MÜHENDİSLİK A.Ş.", "/tr/sirket-bilgileri/ozet/4734-kontrolmatik-teknoloji-enerji-ve-muhendislik-a-s"),
    ("KOZAA", "KOZA ANADOLU METAL MADENCİLİK İŞLETMELERİ A.Ş.", "/tr/sirket-bilgileri/ozet/962-koza-anadolu-metal-madencilik-isletmeleri-a-s"),
    ("KOZAL", "TÜRK ALTIN İŞLETMELERİ A.Ş.", "/tr/sirket-bilgileri/ozet/1428-turk-altin-isletmeleri-a-s"),
    ("KRDMD", "KARDEMİR KARABÜK DEMİR ÇELİK SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/973-kardemir-karabuk-demir-celik-sanayi-ve-ticaret-a-s"),
    ("MAVI", "MAVİ GİYİM SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/3987-mavi-giyim-sanayi-ve-ticaret-a-s"),
    ("MGROS", "MİGROS TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/1004-migros-ticaret-a-s"),
    ("MIATK", "MİA TEKNOLOJİ A.Ş.", "/tr/sirket-bilgileri/ozet/4977-mia-teknoloji-a-s"),
    ("ODAS", "ODAŞ ELEKTRİK ÜRETİM SANAYİ TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/1720-odas-elektrik-uretim-sanayi-ticaret-a-s"),
    ("OTKAR", "OTOKAR OTOMOTİV VE SAVUNMA SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/1018-otokar-otomotiv-ve-savunma-sanayi-a-s"),
    ("OYAKC", "OYAK ÇİMENTO FABRİKALARI A.Ş.", "/tr/sirket-bilgileri/ozet/995-oyak-cimento-fabrikalari-a-s"),
    ("PETKM", "PETKİM PETROKİMYA HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/1026-petkim-petrokimya-holding-a-s"),
    ("PGSUS", "PEGASUS HAVA TAŞIMACILIĞI A.Ş.", "/tr/sirket-bilgileri/ozet/1710-pegasus-hava-tasimaciligi-a-s"),
    ("SAHOL", "HACI ÖMER SABANCI HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/945-haci-omer-sabanci-holding-a-s"),
    ("SASA", "SASA POLYESTER SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/1045-sasa-polyester-sanayi-a-s"),
    ("SISE", "TÜRKİYE ŞİŞE VE CAM FABRİKALARI A.Ş.", "/tr/sirket-bilgileri/ozet/1078-turkiye-sise-ve-cam-fabrikalari-a-s"),
    ("SKBNK", "ŞEKERBANK T.A.Ş.", "/tr/sirket-bilgileri/ozet/2422-sekerbank-t-a-s"),
    ("SMRTG", "SMART GÜNEŞ ENERJİSİ TEKNOLOJİLERİ ARAŞTIRMA GELİŞTİRME ÜRETİM SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/5078-smart-gunes-enerjisi-teknolojileri-arastirma-gelistirme-uretim-sanayi-ve-ticaret-a-s"),
    ("SOKM", "ŞOK MARKETLER TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/4050-sok-marketler-ticaret-a-s"),
    ("TAVHL", "TAV HAVALİMANLARI HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/1059-tav-havalimanlari-holding-a-s"),
    ("TCELL", "TURKCELL İLETİŞİM HİZMETLERİ A.Ş.", "/tr/sirket-bilgileri/ozet/1070-turkcell-iletisim-hizmetleri-a-s"),
    ("THYAO", "TÜRK HAVA YOLLARI A.O.", "/tr/sirket-bilgileri/ozet/1068-turk-hava-yollari-a-o"),
    ("TKFEN", "TEKFEN HOLDİNG A.Ş.", "/tr/sirket-bilgileri/ozet/1061-tekfen-holding-a-s"),
    ("TOASO", "TOFAŞ TÜRK OTOMOBİL FABRİKASI A.Ş.", "/tr/sirket-bilgileri/ozet/1064-tofas-turk-otomobil-fabrikasi-a-s"),
    ("TSKB", "TÜRKİYE SINAİ KALKINMA BANKASI A.Ş.", "/tr/sirket-bilgileri/ozet/2429-turkiye-sinai-kalkinma-bankasi-a-s"),
    ("TTKOM", "TÜRK TELEKOMÜNİKASYON A.Ş.", "/tr/sirket-bilgileri/ozet/1069-turk-telekomunikasyon-a-s"),
    ("TTRAK", "TÜRK TRAKTÖR VE ZİRAAT MAKİNELERİ A.Ş.", "/tr/sirket-bilgileri/ozet/1071-turk-traktor-ve-ziraat-makineleri-a-s"),
    ("TUPRS", "TÜPRAŞ-TÜRKİYE PETROL RAFİNERİLERİ A.Ş.", "/tr/sirket-bilgileri/ozet/1072-tupras-turkiye-petrol-rafinerileri-a-s"),
    ("TURSG", "TÜRKİYE SİGORTA A.Ş.", "/tr/sirket-bilgileri/ozet/1148-turkiye-sigorta-a-s"),
    ("ULKER", "ÜLKER BİSKÜVİ SANAYİ A.Ş.", "/tr/sirket-bilgileri/ozet/1084-ulker-biskuvi-sanayi-a-s"),
    ("VAKBN", "TÜRKİYE VAKIFLAR BANKASI T.A.O.", "/tr/sirket-bilgileri/ozet/2430-turkiye-vakiflar-bankasi-t-a-o"),
    ("VESTL", "VESTEL ELEKTRONİK SANAYİ VE TİCARET A.Ş.", "/tr/sirket-bilgileri/ozet/1088-vestel-elektronik-sanayi-ve-ticaret-a-s"),
    ("YEOTK", "YEO TEKNOLOJİ ENERJİ VE ENDÜSTRİ A.Ş.", "/tr/sirket-bilgileri/ozet/4883-yeo-teknoloji-enerji-ve-endustri-a-s"),
    ("YKBNK", "YAPI VE KREDİ BANKASI A.Ş.", "/tr/sirket-bilgileri/ozet/2431-yapi-ve-kredi-bankasi-a-s"),
    ("ZOREN", "ZORLU ENERJİ ELEKTRİK ÜRETİM A.Ş.", "/tr/sirket-bilgileri/ozet/1096-zorlu-enerji-elektrik-uretim-a-s"),
]


def infer_sector(company_name: str) -> str:
    upper = company_name.upper()
    if "BANKA" in upper:
        return "Bankacılık"
    if "GAYRİMENKUL YATIRIM ORTAKLIĞI" in upper or "GYO" in upper:
        return "Gayrimenkul Yatırım Ortaklığı (GYO)"
    if "SİGORTA" in upper or "EMEKLİLİK" in upper:
        return "Sigorta ve Emeklilik"
    if "HOLDİNG" in upper:
        return "Holding ve Yatırım"
    if "ENERJİ" in upper or "ELEKTRİK" in upper or "GÜNEŞ" in upper:
        return "Enerji ve Elektrik"
    if "TEKNOLOJİ" in upper or "YAZILIM" in upper or "BİLGİSAYAR" in upper or "BİLİŞİM" in upper:
        return "Teknoloji ve Bilişim"
    if "GIDA" in upper or "BİSKÜVİ" in upper or "SÜT" in upper or "UN " in upper or "İÇECEK" in upper:
        return "Gıda ve İçecek"
    if "MAĞAZA" in upper or "MARKET" in upper or "PERAKENDE" in upper:
        return "Perakende Ticaret"
    if "ÇİMENTO" in upper or "BETON" in upper or "SERAMİK" in upper or "CAM" in upper:
        return "Taş, Toprak ve Çimento"
    if "DEMİR" in upper or "ÇELİK" in upper or "METAL" in upper or "BORU" in upper:
        return "Ana Metal Sanayi"
    if "OTOMOTİV" in upper or "OTOMOBİL" in upper or "TRAKTÖR" in upper:
        return "Otomotiv ve Yan Sanayi"
    if "HAVA YOLLARI" in upper or "HAVA TAŞIMACILIĞI" in upper or "HAVALİMAN" in upper or "LOJİSTİK" in upper:
        return "Ulaştırma ve Havacılık"
    if "KİMYA" in upper or "PETROKİMYA" in upper or "PETROL" in upper or "POLYESTER" in upper or "GÜBRE" in upper:
        return "Kimya, Petrol ve Plastik"
    if "İLAÇ" in upper or "SAĞLIK" in upper or "HASTANE" in upper:
        return "Sağlık ve İlaç"
    if "MENKUL DEĞER" in upper or "YATIRIM ORTAKLIĞI" in upper or "FAKTORİNG" in upper or "FİNANSAL KİRALAMA" in upper or "VARLIK YÖNETİM" in upper:
        return "Finansal Kurumlar ve Aracı Kurumlar"
    if "TEKSTİL" in upper or "GİYİM" in upper or "DOKUMA" in upper:
        return "Tekstil ve Giyim"
    if "İNŞAAT" in upper or "YAPI" in upper:
        return "İnşaat ve Bayındırlık"
    return "Sınai, Ticaret ve Hizmet"


def fetch_bist_companies_from_kap() -> list[tuple[str, str, str]]:
    """
    Scrapes the public BIST company directory page from KAP.
    Returns list of (code, title, relative_kap_url) tuples.
    """
    try:
        response = requests.get(
            KAP_BIST_COMPANIES_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "tr-TR,tr;q=0.9",
            },
            timeout=20,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        by_href = defaultdict(list)
        for anchor in soup.find_all("a"):
            href = anchor.get("href", "")
            if "/tr/sirket-bilgileri/ozet/" in href:
                text = anchor.get_text(strip=True)
                if text:
                    by_href[href].append(text)

        extracted: list[tuple[str, str, str]] = []
        for href, texts in by_href.items():
            if len(texts) >= 2:
                raw_codes = texts[0]
                company_title = texts[1]
                for part in raw_codes.split(","):
                    code = part.strip().upper()
                    if re.match(r"^[A-Z0-9]{3,10}$", code):
                        extracted.append((code, company_title, href))

        if len(extracted) >= 100:
            return extracted
    except Exception as exc:
        logger.warning("KAP BIST directory fetch failed, using fallback list: %s", exc)

    return FALLBACK_BIST_COMPANIES


def sync_all_bist_companies(force: bool = False) -> dict:
    """
    Ensures all BIST companies are stored in the database.
    If the database already has >= 100 companies and force=False, skips network sync.
    """
    existing_count = Company.objects.count()
    if existing_count >= 100 and not force:
        return {
            "synced": False,
            "total_companies": existing_count,
            "source": "Kamuyu Aydınlatma Platformu (KAP) — Yerel Veritabanı Önbelleği",
        }

    records = fetch_bist_companies_from_kap()
    seen_codes = set()
    to_create = []
    existing_map = {c.code: c for c in Company.objects.all()}
    to_update = []

    for code, title, rel_url in records:
        if code in seen_codes:
            continue
        seen_codes.add(code)

        full_kap_url = (
            f"{KAP_BASE_URL}{rel_url}" if rel_url.startswith("/") else rel_url
        )
        sector = infer_sector(title)
        is_bist30 = code in BIST30_CODES
        indices = "BIST 30, BIST 100, BIST TÜM" if is_bist30 else "BIST TÜM"

        if code in existing_map:
            obj = existing_map[code]
            obj.name = title
            obj.sector = sector
            obj.kap_url = full_kap_url
            obj.is_bist30 = is_bist30
            obj.indices = indices
            to_update.append(obj)
        else:
            to_create.append(
                Company(
                    code=code,
                    name=title,
                    sector=sector,
                    kap_url=full_kap_url,
                    is_bist30=is_bist30,
                    indices=indices,
                )
            )

    if to_create:
        Company.objects.bulk_create(to_create, ignore_conflicts=True)
    if to_update:
        Company.objects.bulk_update(
            to_update, ["name", "sector", "kap_url", "is_bist30", "indices"]
        )

    total = Company.objects.count()
    return {
        "synced": True,
        "created": len(to_create),
        "updated": len(to_update),
        "total_companies": total,
        "last_updated": timezone.now().isoformat(),
        "source": "Kamuyu Aydınlatma Platformu (KAP - kap.org.tr/tr/bist-sirketler)",
    }
